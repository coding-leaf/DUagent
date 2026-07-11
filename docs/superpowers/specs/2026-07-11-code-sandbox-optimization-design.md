# Code Sandbox Optimization Design Spec

## 1. Context & Objectives
The `CodeSandboxCard` component displays AI-generated programming exercises or provides a free-form coding playground.
Currently:
1. The exercise description (`statement`) is a Markdown string but rendered as plain text, hurting readability.
2. Public test cases overlap in a single line, causing visual clutter.
3. There is no way to choose a language in free sandbox mode (where `problem_id` is absent).
4. The workbench agent does not follow a strict prompt template for formatting exercise statements.

This design document specifies the layout optimization, components modularity (keeping files and functions small), and agent prompt guidelines.

---

## 2. Component Design
To adhere to the 300-line single-file and 50-line single-function restrictions, we will split the rendering into sub-components.

```
+-------------------------------------------------------------+
|  💻 交互式编程沙箱                     [ Language Selector ] |
+-------------------------------------------------------------+
|  题目要求：                                                 |
|  # 题目名称                                                 |
|  ## 背景与描述                                               |
|  ... (Markdown Viewer)                                      |
|                                                             |
|  💡 公开示例 (Public Test Cases):                             |
|  +---------------------------+ +---------------------------+ |
|  | 示例 #1                   | | 示例 #2                   | |
|  | 输入: 5                   | | 输入: 10                  | |
|  | 输出: 15                  | | 输出: 55                  | |
|  +---------------------------+ +---------------------------+ |
+-------------------------------------------------------------+
|  [main.py]                                                  |
|  +-------------------------------------------------------+  |
|  | print("Hello World")                                  |  |
|  +-------------------------------------------------------+  |
+-------------------------------------------------------------+
|  Console Terminal Output                                    |
+-------------------------------------------------------------+
```

### 2.1 Sub-Components to Extract
1. **`LanguageSelector`**: Renders a dropdown select menu if `problemId` is absent; renders a read-only tag if `problemId` is present.
2. **`PublicTestCases`**: Renders the test cases as a grid of rounded cards.

---

## 3. Code Sandbox Templates & Auto-Fill
We define standard templates:
```javascript
const defaultTemplates = {
  c: '#include <stdio.h>\n\nint main() {\n    printf("Hello World\\n");\n    return 0;\n}',
  cpp: '#include <iostream>\n\nint main() {\n    std::cout << "Hello World" << std::endl;\n    return 0;\n}',
  python: 'print("Hello World")',
  java: 'public class Main {\n    public static void main(String[] args) {\n        System.out.println("Hello World");\n    }\n}',
  go: 'package main\n\nimport "fmt"\n\nfunc main() {\n    fmt.Println("Hello World")\n}',
  javascript: 'console.log("Hello World");'
};
```
If the user switches the selected language:
- Clean the current editor code using `.trim()`.
- If the current code is empty or matches one of the templates in any language, replace it with the selected language's template.
- Otherwise, keep the user's custom code intact.

---

## 4. Prompt Specifications
In `agent_service_v2/src/agent_service_v2/agents/prompts.py`, we modify `WORKBENCH_SYSTEM_PROMPT` to guide the model when calling `create_validated_personal_code_problem`:

```markdown
When calling the `create_validated_personal_code_problem` tool:
- The `statement` parameter MUST be written as a clean Markdown document using this format:
  # 题目: [题目名称]
  ## 背景与描述
  [简单明了的背景描述]
  ## 编写要求
  - [要求 1]
  - [要求 2]
  ## 示例
  - **输入**: `[输入样例]`
  - **输出**: `[输出样例]`
  - **解释**: [样例说明]
- Do NOT output template code or compiler blocks inside the statement string, because the code editor below is already populated with the tool's `starter_code`.
```
