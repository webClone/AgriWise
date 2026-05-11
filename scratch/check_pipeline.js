async function main() {
  const chatResp = await fetch('http://localhost:3000/api/agribrain/run', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      plotId: '69fb754f2ab4b04e9f00394c',
      mode: 'chat',
      query: 'What is the water stress on my field?'
    })
  });
  const chat = await chatResp.json();

  // ChatPayload is in explanations
  const cp = chat.explanations;

  // Feature snapshot
  console.log('=== FEATURE SNAPSHOT (IoT) ===');
  const snap = cp?.summary?.feature_snapshot || {};
  for (const [k,v] of Object.entries(snap)) {
    if (k.startsWith('iot_')) {
      console.log('  ' + k + ': ' + v);
    }
  }

  // Data inventory
  console.log('\n=== DATA INVENTORY ===');
  const inv = cp?.data_inventory || {};
  for (const [k,v] of Object.entries(inv)) {
    console.log('  ' + k + ': ' + v);
  }

  // Chat response
  const cr = cp?.arf?.conversational_response;
  if (cr) {
    console.log('\n=== CHAT RESPONSE (first 800) ===');
    console.log(cr.substring(0, 800));
    
    // Check if it cites IoT data
    console.log('\n=== IoT CITATIONS IN RESPONSE ===');
    const lcr = cr.toLowerCase();
    console.log('  "sensor" mentioned:', lcr.includes('sensor'));
    console.log('  "iot" mentioned:', lcr.includes('iot'));
    console.log('  "moisture" mentioned:', lcr.includes('moisture'));
    console.log('  "ground truth" mentioned:', lcr.includes('ground truth'));
    console.log('  "%" mentioned:', (cr.match(/\d+\.?\d*%/g) || []).join(', '));
  }

  // Diagnoses
  console.log('\n=== DIAGNOSES ===');
  for (const dx of (cp?.diagnoses || [])) {
    console.log('  ' + dx.id + ': P=' + dx.prob?.toFixed(3) + ' C=' + dx.conf?.toFixed(3) + ' type=' + dx.type);
  }
}

main().catch(e => console.error('ERROR:', e.message));
