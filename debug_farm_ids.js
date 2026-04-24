const { PrismaClient } = require('@prisma/client');
const { ObjectId } = require('bson');
async function main() {
  const prisma = new PrismaClient();
  const farms = await prisma.farm.findMany({ select: { id: true, name: true } });
  for (const f of farms) {
    const isValid = ObjectId.isValid(f.id);
    let foundOid = false, foundRaw = false;
    try {
      const r1 = await prisma.$runCommandRaw({ find: "Farm", filter: { _id: { $oid: f.id } }, limit: 1 });
      foundOid = r1?.cursor?.firstBatch?.length > 0;
    } catch(e) { /* ignore */ }
    try {
      const r2 = await prisma.$runCommandRaw({ find: "Farm", filter: { _id: f.id }, limit: 1 });
      foundRaw = r2?.cursor?.firstBatch?.length > 0;
    } catch(e) { /* ignore */ }
    console.log(`${f.name.padEnd(25)} | ID: ${f.id} | valid: ${isValid} | $oid: ${foundOid} | raw: ${foundRaw}`);
  }
  await prisma.$disconnect();
}
main();
