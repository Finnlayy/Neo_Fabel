import React from "react";
import { GenerativePlan } from "../types";
import GenerativeGoalPlanningCard from "./GenerativeGoalPlanningCard";
import ResourceAllocationCard from "./ResourceAllocationCard";

interface ResourceAllocationProps {
  allocation: { name: string; value: number }[];
  activePlan: GenerativePlan | null;
  onDeployPlan: (plan: GenerativePlan) => void;
}

export default function ResourceAllocation({ allocation, activePlan, onDeployPlan }: ResourceAllocationProps) {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 font-mono text-xs">
      <GenerativeGoalPlanningCard activePlan={activePlan} onDeployPlan={onDeployPlan} />
      <ResourceAllocationCard allocation={allocation} />
    </div>
  );
}
