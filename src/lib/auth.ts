// Authentication utilities for AgriWise
// Using free OTP simulation for development, can switch to real SMS provider for production

import { prisma } from "./db";

// Generate 6-digit OTP code
export function generateOTP(): string {
  return Math.floor(100000 + Math.random() * 900000).toString();
}

// Validate Algerian phone number
export function validatePhoneNumber(phone: string): boolean {
  // Remove spaces and dashes
  const cleaned = phone.replace(/[\s-]/g, "");
  
  // Algerian phone numbers: 05, 06, 07 followed by 8 digits
  const regex = /^0[567]\d{8}$/;
  return regex.test(cleaned);
}

// Format phone number for display
export function formatPhoneNumber(phone: string): string {
  const cleaned = phone.replace(/[\s-]/g, "");
  if (cleaned.length === 10) {
    return `${cleaned.slice(0, 4)} ${cleaned.slice(4, 6)} ${cleaned.slice(6, 8)} ${cleaned.slice(8)}`;
  }
  return phone;
}

// Store OTP in database (expires in 5 minutes)
export async function createOTP(phone: string): Promise<string> {
  const code = generateOTP();
  const expiresAt = new Date(Date.now() + 5 * 60 * 1000); // 5 minutes
  
  // Delete any existing OTP for this phone
  await prisma.otpCode.deleteMany({
    where: { phone },
  });
  
  // Create new OTP
  await prisma.otpCode.create({
    data: {
      phone,
      code,
      expiresAt,
    },
  });
  
  return code;
}

// Verify OTP code
export async function verifyOTP(phone: string, code: string): Promise<boolean> {
  const otp = await prisma.otpCode.findFirst({
    where: {
      phone,
      code,
      used: false,
      expiresAt: { gt: new Date() },
    },
  });
  
  if (!otp) {
    return false;
  }
  
  // Mark OTP as used
  await prisma.otpCode.update({
    where: { id: otp.id },
    data: { used: true },
  });
  
  return true;
}

// Send OTP via SMS (mock for development, replace with real provider for production)
export async function sendOTP(phone: string): Promise<{ success: boolean; message: string; code?: string }> {
  if (!validatePhoneNumber(phone)) {
    return { success: false, message: "رقم الهاتف غير صالح" };
  }
  
  const code = await createOTP(phone);
  
  if (process.env.NODE_ENV === "development" || process.env.SMS_PROVIDER === "mock") {
    // In development, return the code for testing
    console.log(`[DEV] OTP for ${phone}: ${code}`);
    return { 
      success: true, 
      message: "تم إرسال رمز التحقق (وضع التطوير)",
      code, // Only in dev mode
    };
  }
  
  // Production: Use real SMS provider
  // Options for free/cheap SMS in Algeria:
  // 1. Twilio (free trial credits)
  // 2. Vonage (free trial)
  // 3. Local providers
  
  try {
    if (process.env.SMS_PROVIDER === "twilio") {
      return await sendViaTwilio(phone, code);
    }
    
    // Default: mock mode
    console.log(`[MOCK SMS] OTP for ${phone}: ${code}`);
    return { success: true, message: "تم إرسال رمز التحقق" };
    
  } catch (error) {
    console.error("SMS send error:", error);
    return { success: false, message: "فشل إرسال الرسالة. حاول مرة أخرى." };
  }
}

// Twilio integration (uses TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER)
async function sendViaTwilio(phone: string, code: string): Promise<{ success: boolean; message: string }> {
  const accountSid = process.env.TWILIO_ACCOUNT_SID;
  const authToken = process.env.TWILIO_AUTH_TOKEN;
  const fromNumber = process.env.TWILIO_PHONE_NUMBER;
  
  if (!accountSid || !authToken || !fromNumber) {
    throw new Error("Twilio credentials not configured");
  }
  
  // Format phone for international (Algeria: +213)
  const internationalPhone = `+213${phone.slice(1)}`;
  
  const response = await fetch(
    `https://api.twilio.com/2010-04-01/Accounts/${accountSid}/Messages.json`,
    {
      method: "POST",
      headers: {
        "Authorization": `Basic ${Buffer.from(`${accountSid}:${authToken}`).toString("base64")}`,
        "Content-Type": "application/x-www-form-urlencoded",
      },
      body: new URLSearchParams({
        To: internationalPhone,
        From: fromNumber,
        Body: `رمز التحقق الخاص بك في أجري وايز: ${code}\nصالح لمدة 5 دقائق.`,
      }),
    }
  );
  
  if (!response.ok) {
    throw new Error(`Twilio error: ${response.status}`);
  }
  
  return { success: true, message: "تم إرسال رمز التحقق" };
}

// Get or create user after successful OTP verification
export async function getOrCreateUser(phone: string, data?: { name?: string; wilaya?: string; wilayaCode?: string }) {
  let user = await prisma.user.findUnique({
    where: { phone },
  });
  
  if (!user && data?.name && data?.wilayaCode) {
    user = await prisma.user.create({
      data: {
        phone,
        name: data.name,
        wilaya: data.wilaya || "",
        wilayaCode: data.wilayaCode,
        isVerified: true,
      },
    });
  } else if (user && !user.isVerified) {
    user = await prisma.user.update({
      where: { id: user.id },
      data: { isVerified: true },
    });
  }
  
  return user;
}
