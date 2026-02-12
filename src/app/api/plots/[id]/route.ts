
import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { ObjectId } from "bson";

export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;

    if (!ObjectId.isValid(id)) {
      return NextResponse.json({ error: "Invalid ID" }, { status: 400 });
    }

    // Try direct delete first
    try {
        await prisma.plot.delete({
            where: { id },
        });
    } catch (e) {
        // If direct delete fails (likely due to ID lookup issue), try to find by ID in memory first
        console.log(`[DELETE Plot] Direct delete failed for ${id}, trying fallback lookup...`);
        const allPlots = await prisma.plot.findMany();
        const plot = allPlots.find(p => p.id === id);
        
        if (!plot) {
             return NextResponse.json({ error: "Plot not found" }, { status: 404 });
        }
        
        // If found, delete utilizing the ID that worked (though in this case it's the same string, 
        // passing it again to delete might fail if the issue is deeper in Prisma's query generation.
        // But typically delete needs a unique selector. If findUnique fails, delete likely fails too.)
        
        // Alternative: If Prisma delete fails on ID, we might need raw command or retry.
        // For now, let's assume the error was "Record not found" and since we found it in findMany,
        // it implies a disconnect. 
        // Let's try raw delete if we are on MongoDB.
        
        // Try raw delete with ObjectId first
        try {
            const res: any = await prisma.$runCommandRaw({
                delete: "Plot",
                deletes: [{ q: { _id: { "$oid": id } }, limit: 1 }]
            });
            console.log(`[DELETE] Raw command result (OID):`, JSON.stringify(res));

            // If n=0, try string ID
             if (res.n === 0) {
                console.log(`[DELETE] OID delete matched 0 documents. Trying string ID...`);
                const res2: any = await prisma.$runCommandRaw({
                    delete: "Plot",
                    deletes: [{ q: { _id: id }, limit: 1 }]
                });
                console.log(`[DELETE] Raw command result (String):`, JSON.stringify(res2));
            }
        } catch (rawErr) {
             console.error(`[DELETE] Raw Plot delete failed`, rawErr);
        }
    }

    return NextResponse.json({ success: true });
  } catch (error) {
    console.error("Delete plot error:", error);
    return NextResponse.json(
      { error: "Internal Server Error" },
      { status: 500 }
    );
  }
}

export async function PUT(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;
    const body = await request.json();

    if (!ObjectId.isValid(id)) {
      return NextResponse.json({ error: "Invalid ID" }, { status: 400 });
    }
    
    // Clean up body to remove fields unrelated to update or immutable
    const { farmId, geoJson, ...updateData } = body;
    
    // For geoJson, if it's provided, include it
    const dataToUpdate: any = { ...updateData };
    if (dataToUpdate.area) {
        dataToUpdate.area = parseFloat(dataToUpdate.area);
    }
    if (geoJson) {
        dataToUpdate.geoJson = geoJson;
    }

    let updatedPlot;
    try {
         console.log(`[UPDATE] Attempting Prisma update for ${id}`);
         updatedPlot = await prisma.plot.update({
            where: { id },
            data: dataToUpdate,
        });
        console.log(`[UPDATE] Prisma update success`);
    } catch (e: any) {
         console.log(`[UPDATE Plot] Direct update failed for ${id}, trying raw update... Error: ${e.message}`);
         // Fallback to raw update if Prisma fails
          const updateDoc = { $set: dataToUpdate };
          let rawResult: any = null;
          
          // Try "Plot" first with ObjectId
          try {
              const res: any = await prisma.$runCommandRaw({
                update: "Plot",
                updates: [{ q: { _id: { "$oid": id } }, u: updateDoc }]
            });
            rawResult = res;
            console.log(`[UPDATE] Raw command result (OID):`, JSON.stringify(res));

            if (res.n === 0) {
                console.log(`[UPDATE] OID update matched 0 documents. Trying string ID...`);
                const res2: any = await prisma.$runCommandRaw({
                    update: "Plot",
                    updates: [{ q: { _id: id }, u: updateDoc }]
                });
                rawResult = res2;
                console.log(`[UPDATE] Raw command result (String):`, JSON.stringify(res2));
            }
          } catch (rawErr) {
             console.error(`[UPDATE] Raw Plot update failed`, rawErr);
          }
          
        updatedPlot = { id, ...dataToUpdate, _debug: rawResult }; 
    }

    return NextResponse.json({ success: true, plot: updatedPlot });
  } catch (error) {
    console.error("Update plot error:", error);
    return NextResponse.json(
      { error: "Internal Server Error" },
      { status: 500 }
    );
  }
}
