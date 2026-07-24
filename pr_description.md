# 🧹 [Code Health] Refactor NavigationMenu Component

## Description

🎯 **What:**
Extracted static data, constant configurations, custom hooks, and sub-components out of the main `NavigationMenu` component in `src/components/NavigationMenu.tsx`. The single function `NavigationMenu` was over 200 lines long and has now been significantly simplified.

💡 **Why:**
The main `NavigationMenu` function was excessively long and handled too many responsibilities (static data definition, UI rendering logic, metrics display, keyboard event handling, etc.). Breaking it down improves maintainability, readability, testability, and reduces cognitive load when making changes.

✅ **Verification:**
- Reviewed the final refactored code for syntax and structural correctness.
- Ran `vitest` which confirmed all 28 existing tests passed successfully.
- Fixed an outstanding missing type error in `src/types.ts` (`AgentStatusPacket`) to ensure `npm run lint` passes successfully.

✨ **Result:**
The main `NavigationMenu` function is now only ~30 lines long and uses composition with the newly created `NavigationTabItem` and `MetricsDisplay` components, and logic abstraction using `getTabs` and `useKeyboardNavigation`. Functionality is fully preserved, and readability is immensely improved.
