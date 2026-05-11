const { PrismaClient } = require('@prisma/client');
const p = new PrismaClient();
p.sensor.findMany().then(s => {
  console.log(JSON.stringify(s.map(x => ({
    id: x.id,
    deviceId: x.deviceId,
    type: x.type,
    plotId: x.plotId,
    apiKey: x.apiKey
  })), null, 2));
  p.$disconnect();
});
