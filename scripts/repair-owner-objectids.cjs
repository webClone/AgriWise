const { PrismaClient } = require("@prisma/client");
const { ObjectId } = require("bson");

const prisma = new PrismaClient();
const apply = process.argv.includes("--apply");

async function count(collection, query) {
  const result = await prisma.$runCommandRaw({ count: collection, query });
  return Number(result.n || 0);
}

async function main() {
  const legacyResult = await prisma.$runCommandRaw({
    aggregate: "User",
    pipeline: [
      { $match: { _id: { $type: "string" } } },
      { $project: { _id: 1 } },
    ],
    cursor: {},
  });
  const legacyIds = legacyResult.cursor.firstBatch.map((entry) => entry._id);
  if (legacyIds.length !== 1 || !ObjectId.isValid(legacyIds[0])) {
    throw new Error(`Expected exactly one 24-hex legacy user id; found ${legacyIds.length}`);
  }

  const ownerId = legacyIds[0];
  const users = await prisma.user.findMany();
  const legacyUser = users.find((user) => user.id === ownerId);
  if (!legacyUser) throw new Error("Legacy user could not be decoded through Prisma");

  const stringFarmCount = await count("Farm", { userId: ownerId });
  const objectFarmCount = await count("Farm", { userId: { $oid: ownerId } });
  const canonicalUserCount = await count("User", { _id: { $oid: ownerId } });
  console.log(JSON.stringify({
    mode: apply ? "apply" : "dry-run",
    ownerId,
    legacyUsers: legacyIds.length,
    stringFarmCount,
    objectFarmCount,
    canonicalUserCount,
  }, null, 2));

  if (!apply) return;

  if (canonicalUserCount === 0) {
    const archivedPhone = `legacy-objectid-mismatch-${ownerId}`;
    const archiveResult = await prisma.$runCommandRaw({
      update: "User",
      updates: [{
        q: { _id: ownerId },
        u: {
          $set: {
            phone: archivedPhone,
            isActive: false,
            objectIdMigrationStatus: "retained_recovery_record",
          },
        },
        multi: false,
      }],
    });
    if (Number(archiveResult.n || 0) !== 1) {
      throw new Error("Could not reserve the legacy user's unique phone");
    }

    try {
      await prisma.user.create({
        data: {
          id: ownerId,
          phone: legacyUser.phone,
          name: legacyUser.name,
          nameAr: legacyUser.nameAr,
          email: legacyUser.email,
          role: legacyUser.role,
          wilaya: legacyUser.wilaya,
          wilayaCode: legacyUser.wilayaCode,
          commune: legacyUser.commune,
          language: legacyUser.language,
          isVerified: legacyUser.isVerified,
          isActive: legacyUser.isActive,
          ...(legacyUser.profile !== null ? { profile: legacyUser.profile } : {}),
          createdAt: legacyUser.createdAt,
          updatedAt: legacyUser.updatedAt,
        },
      });
    } catch (error) {
      await prisma.$runCommandRaw({
        update: "User",
        updates: [{
          q: { _id: ownerId },
          u: {
            $set: { phone: legacyUser.phone, isActive: legacyUser.isActive },
            $unset: { objectIdMigrationStatus: "" },
          },
          multi: false,
        }],
      });
      throw error;
    }
  }

  if (stringFarmCount > 0) {
    const updateResult = await prisma.$runCommandRaw({
      update: "Farm",
      updates: [{
        q: { userId: ownerId },
        u: { $set: { userId: { $oid: ownerId } } },
        multi: true,
      }],
    });
    if (Number(updateResult.n || 0) !== stringFarmCount) {
      throw new Error(`Expected to update ${stringFarmCount} farms; updated ${updateResult.n || 0}`);
    }
  }

  const canonicalUser = await prisma.user.findUnique({ where: { id: ownerId } });
  const canonicalFarms = await prisma.farm.findMany({
    where: { userId: ownerId },
    select: { id: true, _count: { select: { plots: true } } },
  });
  const remainingStringFarms = await count("Farm", { userId: ownerId });
  const finalObjectFarms = await count("Farm", { userId: { $oid: ownerId } });
  const plotCount = canonicalFarms.reduce((total, farm) => total + farm._count.plots, 0);

  if (!canonicalUser || remainingStringFarms !== 0 || finalObjectFarms !== 7 || plotCount !== 15) {
    throw new Error("Owner migration verification failed");
  }

  console.log(JSON.stringify({
    status: "verified",
    canonicalFarmCount: canonicalFarms.length,
    canonicalPlotCount: plotCount,
    remainingStringFarms,
    retainedLegacyRecoveryRecord: true,
  }, null, 2));
}

main()
  .catch((error) => {
    console.error(error);
    process.exitCode = 1;
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
