
import { NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { ObjectId } from "bson";
import {
  authenticatedUserId,
  userOwnsTask,
} from "@/lib/tenant-authorization";

// PUT /api/cycles/[id]/tasks - Update a task
export async function PUT(
  req: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const userId = await authenticatedUserId();
    if (!userId) {
      return NextResponse.json(
        { error: "Authentication required" },
        { status: 401 },
      );
    }
    const { id: taskId } = await params;
    
    if (!ObjectId.isValid(taskId)) {
        return NextResponse.json({ error: "Invalid Task ID" }, { status: 400 });
    }

    const body = await req.json();
    const { completed } = body;
    if (typeof completed !== "boolean") {
      return NextResponse.json(
        { error: "completed must be boolean" },
        { status: 400 },
      );
    }
    if (!await userOwnsTask(userId, taskId)) {
      return NextResponse.json({ error: "Task not found" }, { status: 404 });
    }

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
