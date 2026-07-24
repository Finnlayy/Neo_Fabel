import React from "react";
import { AgentStatusPacket, GenerativePlan } from "../types";
import GenerativeGoalPlanningCard from "./GenerativeGoalPlanningCard";
import ResourceAllocationCard from "./ResourceAllocationCard";

interface ResourceAllocationProps {
  allocation: { name: string; value: number }[];
  activePlan: GenerativePlan | null;
  onDeployPlan: (plan: GenerativePlan) => void;
  agentStatusPackets?: AgentStatusPacket[];
}

export default function ResourceAllocation({
  allocation,
  activePlan,
  onDeployPlan,
  agentStatusPackets = [],
}: ResourceAllocationProps) {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 font-mono text-xs">
      <GenerativeGoalPlanningCard
        activePlan={activePlan}
        onDeployPlan={onDeployPlan}
        agentStatusPackets={agentStatusPackets}
      />
      <ResourceAllocationCard allocation={allocation} />
    </div>
  );
}
