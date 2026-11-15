import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { authenticatedUserId } from "@/lib/tenant-authorization";
import { validateGeometryRevisionInput } from "@/lib/agribrain/geometry-registration-policy.mjs";
import {
  geometryIntegrityDigest,
  projectWorkspaceGeometryRegistration,
} from "@/lib/agribrain/geometry-registration-projection.mjs";
import { validateParcelContainment } from "../route";

const objectIdRegex = /^[a-f\d]{24}$/i;

async function authorizedScope(rawPlotId: string, userId: string) {
  const plot = await prisma.plot.findFirst({
    where: { id: rawPlotId, farm: { userId } },
    select: {
      id: true,
      geoJson: true,
      farm: { select: { id: true, userId: true } },
    },
  });
  return plot
    ? {
        tenantId: plot.farm.userId,
        farmId: plot.farm.id,
        plotId: plot.id,
        geoJson: plot.geoJson,
      }
    : null;
}

export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ id: string; regId: string }> }
) {
  try {
    const userId = await authenticatedUserId();
    if (!userId) return NextResponse.json({ error: "Authentication required" }, { status: 401 });
    const { id: plotId, regId } = await params;
    if (!objectIdRegex.test(plotId)) {
      return NextResponse.json({ error: "Resource not found" }, { status: 404 });
    }
    const scope = await authorizedScope(plotId, userId);
    if (!scope) return NextResponse.json({ error: "Plot not found" }, { status: 404 });

    const record = await prisma.workspaceGeometryRegistration.findFirst({
      where: objectIdRegex.test(regId)
        ? { id: regId, plotId: scope.plotId }
        : { plotId: scope.plotId, OR: [{ entityId: regId }, { registrationKey: regId }] },
    });
    if (!record) return NextResponse.json({ error: "Geometry registration not found" }, { status: 404 });

    const entity = projectWorkspaceGeometryRegistration(record as any, scope);
    return NextResponse.json({
      success: true,
      registration: record,
      entity,
      authority: "OWNER_DECLARED_NOT_SCIENTIFICALLY_ADMITTED",
    });
  } catch (error) {
    console.error("[workspace/geometries/[regId]:GET]", error);
    return NextResponse.json({ error: "Unable to fetch geometry registration" }, { status: 500 });
  }
}

export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ id: string; regId: string }> }
) {
  try {
    const userId = await authenticatedUserId();
    if (!userId) return NextResponse.json({ error: "Authentication required" }, { status: 401 });
    const { id: plotId, regId } = await params;
    if (!objectIdRegex.test(plotId)) {
      return NextResponse.json({ error: "Resource not found" }, { status: 404 });
    }
    const scope = await authorizedScope(plotId, userId);
    if (!scope) return NextResponse.json({ error: "Plot not found" }, { status: 404 });

    const record = await prisma.workspaceGeometryRegistration.findFirst({
      where: objectIdRegex.test(regId)
        ? { id: regId, plotId: scope.plotId }
        : { plotId: scope.plotId, OR: [{ entityId: regId }, { registrationKey: regId }] },
    });
    if (!record) return NextResponse.json({ error: "Geometry registration not found" }, { status: 404 });
    if (record.status !== "OWNER_DECLARED") {
      return NextResponse.json(
        { error: "Cannot revise a revoked or non-active geometry registration" },
        { status: 400 }
      );
    }

    let raw: unknown;
    try {
      raw = await request.json();
    } catch {
      return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
    }

    const validation = validateGeometryRevisionInput(raw, record.entityKind);
    if (!validation.ok) return NextResponse.json({ error: validation.error }, { status: 400 });

    const input = validation.value;

    // Validate parcel footprint containment if geometry is being revised
    if (input.geometry) {
      const containment = validateParcelContainment(input.geometry, scope.geoJson);
      if (!containment.ok) {
        return NextResponse.json({ error: containment.error }, { status: 400 });
      }
    }

    // Strict optimistic concurrency check
    if (input.expected_revision !== record.revision) {
      return NextResponse.json(
        {
          error: "Revision conflict: the geometry has been modified by another operation",
          expected_revision: input.expected_revision,
          current_revision: record.revision,
        },
        { status: 409 }
      );
    }

    const nextRevision = record.revision + 1;
    const nextGeometry = (input.geometry || record.geometry) as any;
    const nextDigest = input.geometry
      ? geometryIntegrityDigest(input.geometry)
      : record.geometryDigest;
    const nextName = input.label !== null && input.label !== undefined ? input.label : record.name;
    const nextNotes = input.notes !== undefined ? input.notes : record.notes;

    // Execute mutation and audit log insertion inside an atomic database transaction
    let updatedRecord: any = null;
    try {
      updatedRecord = await prisma.$transaction(async (tx) => {
        const updateResult = await tx.workspaceGeometryRegistration.updateMany({
          where: {
            id: record.id,
            plotId: scope.plotId,
            status: "OWNER_DECLARED", // Strict active predicate prevents race with concurrent DELETE
            revision: input.expected_revision,
          },
          data: {
            revision: nextRevision,
            geometry: nextGeometry,
            geometryDigest: nextDigest,
            name: nextName,
            notes: nextNotes,
            updatedAt: new Date(),
          },
        });

        if (updateResult.count === 0) {
          throw new Error("REVISION_CONFLICT");
        }

        await tx.workspaceGeometryRevision.create({
          data: {
            registrationId: record.id,
            plotId: scope.plotId,
            revision: nextRevision,
            operation: "UPDATE",
            geometry: nextGeometry,
            geometryDigest: nextDigest,
            name: nextName,
            notes: nextNotes,
            editorId: userId,
          },
        });

        const updated = await tx.workspaceGeometryRegistration.findUnique({
          where: { id: record.id },
        });
        return updated;
      });
    } catch (err: any) {
      if (err.message === "REVISION_CONFLICT" || err.code === "P2002" || err.code === "P2034") {
        const latest = await prisma.workspaceGeometryRegistration.findUnique({
          where: { id: record.id },
          select: { revision: true, status: true },
        });
        return NextResponse.json(
          {
            error: "Revision conflict: the geometry has been modified or revoked by another concurrent operation",
            expected_revision: input.expected_revision,
            current_revision: latest?.revision ?? record.revision,
            current_status: latest?.status ?? record.status,
          },
          { status: 409 }
        );
      }
      throw err;
    }

    const entity = projectWorkspaceGeometryRegistration(updatedRecord as any, scope);
    return NextResponse.json({
      success: true,
      current_revision: nextRevision,
      entity,
      authority: "OWNER_DECLARED_NOT_SCIENTIFICALLY_ADMITTED",
    });
  } catch (error) {
    console.error("[workspace/geometries/[regId]:PATCH]", error);
    return NextResponse.json({ error: "Unable to revise geometry registration" }, { status: 500 });
  }
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ id: string; regId: string }> }
) {
  try {
    const userId = await authenticatedUserId();
    if (!userId) return NextResponse.json({ error: "Authentication required" }, { status: 401 });
    const { id: plotId, regId } = await params;
    if (!objectIdRegex.test(plotId)) {
      return NextResponse.json({ error: "Resource not found" }, { status: 404 });
    }
    const scope = await authorizedScope(plotId, userId);
    if (!scope) return NextResponse.json({ error: "Plot not found" }, { status: 404 });

    const record = await prisma.workspaceGeometryRegistration.findFirst({
      where: objectIdRegex.test(regId)
        ? { id: regId, plotId: scope.plotId }
        : { plotId: scope.plotId, OR: [{ entityId: regId }, { registrationKey: regId }] },
    });
    if (!record) return NextResponse.json({ error: "Geometry registration not found" }, { status: 404 });
    if (record.status === "REVOKED") {
      return NextResponse.json({ error: "Geometry registration is already revoked" }, { status: 409 });
    }

    let rawBody: any = {};
    try {
      const text = await request.text();
      if (text) rawBody = JSON.parse(text);
    } catch {
      return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
    }

    // expected_revision is MANDATORY for revocation to prevent concurrent revocation/edit races
    if (
      rawBody.expected_revision === undefined ||
      typeof rawBody.expected_revision !== "number" ||
      !Number.isInteger(rawBody.expected_revision) ||
      rawBody.expected_revision < 1
    ) {
      return NextResponse.json(
        { error: "expected_revision is required and must be a positive integer" },
        { status: 400 }
      );
    }

    if (rawBody.expected_revision !== record.revision) {
      return NextResponse.json(
        {
          error: "Revision conflict: the geometry has been modified by another operation",
          expected_revision: rawBody.expected_revision,
          current_revision: record.revision,
        },
        { status: 409 }
      );
    }

    const nextRevision = record.revision + 1;
    const reasonText = rawBody.reason ? String(rawBody.reason).slice(0, 500) : null;

    // Atomic transaction for revocation and audit record
    try {
      await prisma.$transaction(async (tx) => {
        const updateResult = await tx.workspaceGeometryRegistration.updateMany({
          where: {
            id: record.id,
            plotId: scope.plotId,
            status: "OWNER_DECLARED", // Strict active predicate prevents double-revocation or race
            revision: rawBody.expected_revision,
          },
          data: {
            status: "REVOKED",
            revision: nextRevision,
            updatedAt: new Date(),
          },
        });

        if (updateResult.count === 0) {
          throw new Error("REVOCATION_CONFLICT");
        }

        await tx.workspaceGeometryRevision.create({
          data: {
            registrationId: record.id,
            plotId: scope.plotId,
            revision: nextRevision,
            operation: "REVOKE",
            geometry: record.geometry as any,
            geometryDigest: record.geometryDigest,
            name: record.name,
            notes: reasonText ? `REVOKED: ${reasonText}` : "REVOKED",
            editorId: userId,
          },
        });
      });
    } catch (err: any) {
      if (err.message === "REVOCATION_CONFLICT" || err.code === "P2002" || err.code === "P2034") {
        const latest = await prisma.workspaceGeometryRegistration.findUnique({
          where: { id: record.id },
          select: { revision: true, status: true },
        });
        return NextResponse.json(
          {
            error: "Revocation conflict: the geometry has been modified or revoked by another concurrent operation",
            expected_revision: rawBody.expected_revision,
            current_revision: latest?.revision ?? record.revision,
            current_status: latest?.status ?? record.status,
          },
          { status: 409 }
        );
      }
      throw err;
    }

    return NextResponse.json({
      success: true,
      message: "Geometry registration soft-revoked; historical audit trail preserved",
      registration_id: record.id,
      final_revision: nextRevision,
      status: "REVOKED",
    });
  } catch (error) {
    console.error("[workspace/geometries/[regId]:DELETE]", error);
    return NextResponse.json({ error: "Unable to revoke geometry registration" }, { status: 500 });
  }
}
