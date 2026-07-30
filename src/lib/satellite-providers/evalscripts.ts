/**
 * Sentinel Hub Evalscripts — Client-safe constants
 * 
 * Extracted from sentinel-service.ts so client components can import
 * evalscripts without pulling in server-only fetch code.
 */

export const EVALSCRIPTS = {
  'true-color': `//VERSION=3\nfunction setup(){return{input:["B02","B03","B04","dataMask"],output:[{id:"default",bands:3,sampleType:"AUTO"},{id:"dataMask",bands:1,sampleType:"UINT8"}]};}\nfunction evaluatePixel(sample){return{default:[sample.B04*2.5,sample.B03*2.5,sample.B02*2.5],dataMask:[sample.dataMask]};}`,
  
  'false-color': `//VERSION=3\nfunction setup(){return{input:["B08","B04","B03","dataMask"],output:[{id:"default",bands:3,sampleType:"AUTO"},{id:"dataMask",bands:1,sampleType:"UINT8"}]};}\nfunction evaluatePixel(sample){return{default:[sample.B08*2.5,sample.B04*2.5,sample.B03*2.5],dataMask:[sample.dataMask]};}`,
  
  'nir-r-g': `//VERSION=3\nfunction setup(){return{input:["B08","B04","B03","dataMask"],output:[{id:"default",bands:3,sampleType:"AUTO"},{id:"dataMask",bands:1,sampleType:"UINT8"}]};}\nfunction evaluatePixel(sample){return{default:[sample.B08*2.5,sample.B04*2.5,sample.B03*2.5],dataMask:[sample.dataMask]};}`,
  
  'ndvi': `//VERSION=3\nfunction setup(){return{input:["B04","B08","dataMask"],output:[{id:"default",bands:3},{id:"dataMask",bands:1,sampleType:"UINT8"}]};}function evaluatePixel(sample){var v=(sample.B08-sample.B04)/(sample.B08+sample.B04);var c=[0,0,0];if(v<0)c=[0.4,0.4,0.4];else if(v<0.2)c=[0.6,0.3,0];else if(v<0.4)c=[0.8,0.7,0.2];else if(v<0.6)c=[0.4,0.8,0.2];else c=[0,0.5,0];return{default:c,dataMask:[sample.dataMask]};}`,
  
  'evi': `//VERSION=3\nfunction setup(){return{input:["B02","B04","B08","dataMask"],output:[{id:"default",bands:3},{id:"dataMask",bands:1,sampleType:"UINT8"}]};}function evaluatePixel(sample){var v=2.5*((sample.B08-sample.B04)/(sample.B08+6*sample.B04-7.5*sample.B02+1));var c=[0,0,0];if(v<0)c=[0.5,0,0];else if(v<0.2)c=[0.9,0.5,0.2];else if(v<0.4)c=[0.7,0.8,0.2];else if(v<0.6)c=[0.3,0.7,0.2];else c=[0,0.5,0];return{default:c,dataMask:[sample.dataMask]};}`,
  
  'savi': `//VERSION=3\nfunction setup(){return{input:["B04","B08","dataMask"],output:[{id:"default",bands:3},{id:"dataMask",bands:1,sampleType:"UINT8"}]};}function evaluatePixel(sample){var v=((sample.B08-sample.B04)/(sample.B08+sample.B04+0.5))*1.5;var c=[0,0,0];if(v<0)c=[0.5,0,0];else if(v<0.2)c=[0.9,0.5,0.2];else if(v<0.4)c=[0.7,0.8,0.2];else if(v<0.6)c=[0.3,0.7,0.2];else c=[0,0.5,0];return{default:c,dataMask:[sample.dataMask]};}`,
  
  'ndmi': `//VERSION=3\nfunction setup(){return{input:["B08","B11","dataMask"],output:[{id:"default",bands:3},{id:"dataMask",bands:1,sampleType:"UINT8"}]};}function evaluatePixel(sample){var v=(sample.B08-sample.B11)/(sample.B08+sample.B11);var c=[0,0,0];if(v<0)c=[0.9,0.9,0.9];else if(v<0.1)c=[0.7,0.8,0.9];else if(v<0.3)c=[0.3,0.5,0.9];else c=[0,0.2,0.6];return{default:c,dataMask:[sample.dataMask]};}`,
  
  'moisture-index': `//VERSION=3\nfunction setup(){return{input:["B08","B11","dataMask"],output:[{id:"default",bands:3},{id:"dataMask",bands:1,sampleType:"UINT8"}]};}function evaluatePixel(sample){var v=(sample.B08-sample.B11)/(sample.B08+sample.B11);var c=[0,0,0];if(v<0)c=[0.9,0.9,0.9];else if(v<0.1)c=[0.7,0.8,0.9];else if(v<0.3)c=[0.3,0.5,0.9];else c=[0,0.2,0.6];return{default:c,dataMask:[sample.dataMask]};}`,
  
  'moisture-stress': `//VERSION=3\nfunction setup(){return{input:["B08","B11","dataMask"],output:[{id:"default",bands:3},{id:"dataMask",bands:1,sampleType:"UINT8"}]};}function evaluatePixel(sample){var v=(sample.B08-sample.B11)/(sample.B08+sample.B11);var c=[0,0,0];if(v<-0.1)c=[0.9,0.3,0.2];else if(v<0.1)c=[0.9,0.6,0.3];else if(v<0.3)c=[0.5,0.7,0.8];else c=[0.2,0.4,0.8];return{default:c,dataMask:[sample.dataMask]};}`,
  
  'ndwi': `//VERSION=3\nfunction setup(){return{input:["B03","B08","dataMask"],output:[{id:"default",bands:3},{id:"dataMask",bands:1,sampleType:"UINT8"}]};}function evaluatePixel(sample){var v=(sample.B03-sample.B08)/(sample.B03+sample.B08);var c=[0,0,0];if(v<-0.2)c=[0.95,0.95,0.95];else if(v<0)c=[0.8,0.8,1];else if(v<0.2)c=[0.3,0.5,1];else c=[0,0.1,0.7];return{default:c,dataMask:[sample.dataMask]};}`,
  
  'agriculture': `//VERSION=3\nfunction setup(){return{input:["B11","B08","B02","dataMask"],output:[{id:"default",bands:3,sampleType:"AUTO"},{id:"dataMask",bands:1,sampleType:"UINT8"}]};}\nfunction evaluatePixel(sample){return{default:[sample.B11*2.5,sample.B08*2.5,sample.B02*2.5],dataMask:[sample.dataMask]};}`,
  
  'barren-soil': `//VERSION=3\nfunction setup(){return{input:["B11","B12","B02","dataMask"],output:[{id:"default",bands:3,sampleType:"AUTO"},{id:"dataMask",bands:1,sampleType:"UINT8"}]};}\nfunction evaluatePixel(sample){return{default:[sample.B11*2.5,sample.B12*2.5,sample.B02*2.5],dataMask:[sample.dataMask]};}`
} as const;
