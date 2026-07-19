import React from "react";
import {cleanup, fireEvent, render, screen} from "@testing-library/react";
import {afterEach, describe, expect, it, vi} from "vitest";
import NavigationMenu from "./NavigationMenu";

describe("NavigationMenu", () => {
  afterEach(() => cleanup());

  it("renders nine workspace tabs including Agency", () => {
    render(
      <NavigationMenu
        activeTab="dashboard"
        setActiveTab={() => {}}
        isComplianceActive={false}
        activeSymbol="BTC"
        winLossRatio="1.0"
        executedCount={0}
      />,
    );
    expect(screen.getByRole("tab", {name: /Omni-Dashboard/i})).toBeTruthy();
    expect(screen.getByRole("tab", {name: /Chronos Agent/i})).toBeTruthy();
    expect(screen.getByRole("tab", {name: /Agency/i})).toBeTruthy();
    expect(screen.getAllByRole("tab")).toHaveLength(9);
  });

  it("hotkey 7 selects onnx tab", () => {
    const setActiveTab = vi.fn();
    render(
      <NavigationMenu
        activeTab="dashboard"
        setActiveTab={setActiveTab}
        isComplianceActive={false}
        activeSymbol="BTC"
        winLossRatio="1.0"
        executedCount={0}
      />,
    );
    fireEvent.keyDown(window, {key: "7"});
    expect(setActiveTab).toHaveBeenCalledWith("onnx");
  });

  it("hotkey 8 selects chronos tab", () => {
    const setActiveTab = vi.fn();
    render(
      <NavigationMenu
        activeTab="dashboard"
        setActiveTab={setActiveTab}
        isComplianceActive={false}
        activeSymbol="BTC"
        winLossRatio="1.0"
        executedCount={0}
      />,
    );
    fireEvent.keyDown(window, {key: "8"});
    expect(setActiveTab).toHaveBeenCalledWith("chronos");
  });

  it("hotkey 9 selects agency tab", () => {
    const setActiveTab = vi.fn();
    render(
      <NavigationMenu
        activeTab="dashboard"
        setActiveTab={setActiveTab}
        isComplianceActive={false}
        activeSymbol="BTC"
        winLossRatio="1.0"
        executedCount={0}
      />,
    );
    fireEvent.keyDown(window, {key: "9"});
    expect(setActiveTab).toHaveBeenCalledWith("agency");
  });
});
