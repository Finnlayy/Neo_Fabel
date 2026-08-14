import React from "react";
import {cleanup, fireEvent, render, screen} from "@testing-library/react";
import {afterEach, describe, expect, it, vi} from "vitest";
import NavigationMenu from "./NavigationMenu";

describe("NavigationMenu", () => {
  afterEach(() => cleanup());

  it("renders eleven workspace tabs including Positions", () => {
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
    expect(screen.getByRole("tab", {name: /Positions/i})).toBeTruthy();
    expect(screen.getByRole("tab", {name: /Paper Performance/i})).toBeTruthy();
    expect(screen.getByRole("tab", {name: /Chronos Agent/i})).toBeTruthy();
    expect(screen.getByRole("tab", {name: /Agency/i})).toBeTruthy();
    expect(screen.getAllByRole("tab")).toHaveLength(11);
  });

  it("hotkey P selects positions tab", () => {
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
    fireEvent.keyDown(window, {key: "p"});
    expect(setActiveTab).toHaveBeenCalledWith("positions");
  });

  it("hotkey 0 selects paper tab", () => {
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
    fireEvent.keyDown(window, {key: "0"});
    expect(setActiveTab).toHaveBeenCalledWith("paper");
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

  it("renders Signal Routes tab with TradingView & MCP ingress description", () => {
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
    const signalsTab = screen.getByRole("tab", {name: /Signal Routes/i});
    expect(signalsTab).toBeTruthy();
    expect(signalsTab.getAttribute("title")).toMatch(/TradingView & MCP ingress/i);
  });

  it("hotkey 5 selects signals tab", () => {
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
    fireEvent.keyDown(window, {key: "5"});
    expect(setActiveTab).toHaveBeenCalledWith("signals");
  });

  it("suppresses hotkey 5 while focus is in an input", () => {
    const setActiveTab = vi.fn();
    render(
      <>
        <input aria-label="route name" />
        <NavigationMenu
          activeTab="dashboard"
          setActiveTab={setActiveTab}
          isComplianceActive={false}
          activeSymbol="BTC"
          winLossRatio="1.0"
          executedCount={0}
        />
      </>,
    );
    const input = screen.getByLabelText("route name");
    input.focus();
    fireEvent.keyDown(input, {key: "5"});
    expect(setActiveTab).not.toHaveBeenCalled();
  });

  it("suppresses hotkey 5 while focus is inside a dialog", () => {
    const setActiveTab = vi.fn();
    render(
      <>
        <div role="dialog">
          <button type="button">Confirm bypass</button>
        </div>
        <NavigationMenu
          activeTab="dashboard"
          setActiveTab={setActiveTab}
          isComplianceActive={false}
          activeSymbol="BTC"
          winLossRatio="1.0"
          executedCount={0}
        />
      </>,
    );
    const btn = screen.getByRole("button", {name: /Confirm bypass/i});
    btn.focus();
    fireEvent.keyDown(btn, {key: "5"});
    expect(setActiveTab).not.toHaveBeenCalled();
  });
});
