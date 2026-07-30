"use server";

import { prisma } from "@/lib/prisma";
import { EquipmentType } from "@prisma/client";
import { revalidatePath } from "next/cache";

export type EquipmentState = {
  success: boolean;
  message?: string;
  errors?: {
    name?: string[];
    type?: string[];
    condition?: string[];
    quantity?: string[];
  };
};

export async function addEquipment(
  farmId: string, 
  prevState: EquipmentState, 
  formData: FormData
): Promise<EquipmentState> {
  const name = formData.get("name") as string;
  const type = formData.get("type") as EquipmentType;
  const condition = formData.get("condition") as string;
  const quantity = parseInt(formData.get("quantity") as string);

  if (!name || !type) {
    return {
      success: false,
      message: "Please fill in all required fields.",
    };
  }

  try {
    await prisma.equipment.create({
      data: {
        farmId,
        name,
        type,
        condition,
        quantity: quantity || 1,
      },
    });

    revalidatePath(`/farm/${farmId}`);
    return { success: true, message: "Equipment added successfully" };
  } catch (error) {
    console.error("Failed to add equipment:", error);
    return { success: false, message: `Failed to add equipment: ${(error as Error).message}` };
  }
}

export async function deleteEquipment(equipmentId: string, farmId: string) {
  try {
    await prisma.equipment.delete({
      where: { id: equipmentId },
    });
    revalidatePath(`/farm/${farmId}`);
    return { success: true };
  } catch (_) {
    return { success: false, message: "Failed to delete equipment" };
  }
}

export async function updateEquipment(
  equipmentId: string, 
  farmId: string, 
  prevState: EquipmentState, 
  formData: FormData
): Promise<EquipmentState> {
  const name = formData.get("name") as string;
  const type = formData.get("type") as EquipmentType;
  const condition = formData.get("condition") as string;
  const quantity = parseInt(formData.get("quantity") as string);

  try {
    await prisma.equipment.update({
      where: { id: equipmentId },
      data: {
        name,
        type,
        condition,
        quantity,
      },
    });

    revalidatePath(`/farm/${farmId}`);
    return { success: true, message: "Equipment updated successfully" };
  } catch (_) {
    return { success: false, message: "Failed to update equipment" };
  }
}
