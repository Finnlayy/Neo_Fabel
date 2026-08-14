//! Fable MCP — prompt snapshot builder, next-bar execution, stdio JSON-RPC server.

pub mod blindfold;
pub mod bridge;
pub mod execution;
pub mod mcp_server;
pub mod prompt_builder;

pub use bridge::{BridgeConfig, BridgePostResult, PaperBridge};
pub use execution::{ExecutionConfig, ExecutionEngine, FillEvent, PositionSide};
pub use mcp_server::McpServer;
pub use prompt_builder::{OnnxScore, PromptBuilder, PromptSnapshot, RnaContext};
