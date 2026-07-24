🧹 [code health improvement] extract GeminiChatbot components

🎯 What: Extracted ChatHeader, ChatMessageFeed, PromptSuggestions, and ChatInput components from the main GeminiChatbot function.
💡 Why: GeminiChatbot was over 300 lines long and hard to read. Extracting components improves maintainability.
✅ Verification: Read the source file visually, built the code successfully, and ran tests (28 passed). Also checked git diff.
✨ Result: A much more readable GeminiChatbot component and more focused subcomponents.
