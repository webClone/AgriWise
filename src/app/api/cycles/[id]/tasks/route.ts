
import { NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { ObjectId } from "bson";

// PUT /api/cycles/[id]/tasks - Update a task
export async function PUT(
  req: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id: taskId } = await params;
    
    if (!ObjectId.isValid(taskId)) {
        return NextResponse.json({ error: "Invalid Task ID" }, { status: 400 });
    }

    const body = await req.json();
    const { completed } = body;

    const task = await prisma.cropTask.update({
        where: { id: taskId },
        data: { 
            completed,
            completedAt: completed ? new Date() : null
        }
    });

    return NextResponse.json({ success: true, task });

  } catch (error) {
    console.error("Error updating task:", error);
    return NextResponse.json(
      { error: "Error updating task" }, 
      { status: 500 }
    );
  }
}
