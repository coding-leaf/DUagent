import re

with open('src/pages/AIChat.jsx', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add useMemo to react imports
content = re.sub(
    r"import \{ useState, useEffect, useRef \} from 'react';",
    r"import { useState, useEffect, useRef, useMemo } from 'react';",
    content
)

# 2. Fix setTimeout anti-pattern
content = re.sub(
    r"setTimeout\(\(\) => setResources\(\[\]\), 0\);",
    r"setResources([]);",
    content
)

# 3. Fix scroll behavior performance
scroll_pattern = r"  useEffect\(\(\) => \{\n    // Note: Can cause layout thrashing on fast streams\. Throttle wrapper advised later\.\n    messagesEndRef\.current\?\.scrollIntoView\(\{ behavior: 'smooth' \}\);\n  \}, \[messages\]\);"
scroll_repl = """  // Handle auto-scroll down for incoming chunked text.
  useEffect(() => {
    const frameId = requestAnimationFrame(() => {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    });
    return () => cancelAnimationFrame(frameId);
  }, [messages]);"""
content = re.sub(scroll_pattern, scroll_repl, content)

# 4 & 5. Replace handlers and add handleTextareaChange
handlers_pattern = r"  const handleRegenerate = \(\) => regenerate\(\);\n\n  const handleEditSubmit = \(newContent\) => \{\n    editMessage\(newContent\);\n    setEditingMsg\(null\);\n  \};\n\n  const handleDeleteSession = \(id\) => \{\n    deleteSession\(id\);\n  \};"
handlers_repl = """  const handleEditSubmit = (newContent) => {
    editMessage(newContent);
    setEditingMsg(null);
  };

  const handleTextareaChange = (e) => {
    setInputValue(e.target.value);
    e.target.style.height = 'auto';
    e.target.style.height = Math.min(e.target.scrollHeight, 128) + 'px';
  };"""
content = re.sub(handlers_pattern, handlers_repl, content)

# Replace handleDeleteSession with deleteSession in JSX
content = re.sub(
    r"handleDeleteSession\(session\.id\);",
    r"deleteSession(session.id);",
    content
)

# Replace handleRegenerate with regenerate in JSX
content = re.sub(
    r"onClick=\{handleRegenerate\}",
    r"onClick={regenerate}",
    content
)

# 6. useMemo for knowledge points and resources
memo_pattern = r"  const getActiveKnowledgePoints = \(\) => \{\n    for \(let i = messages\.length - 1; i >= 0; i--\) \{\n      const msg = messages\[i\];\n      if \(msg\.role === 'assistant' && msg\.knowledge_points && msg\.knowledge_points\.length > 0\) \{\n        return msg\.knowledge_points;\n      \}\n    \}\n    return \[\];\n  \};\n\n  const activeKPs = getActiveKnowledgePoints\(\);\n  const recommendedResources = resources\.filter\(res => \{\n    if \(activeKPs\.length === 0\) return true; // Show all if no knowledge points mentioned yet\n    return activeKPs\.some\(kp => \n      res\.knowledge_point\?\.toLowerCase\(\)\.includes\(kp\.toLowerCase\(\)\) \|\|\n      res\.title\?\.toLowerCase\(\)\.includes\(kp\.toLowerCase\(\)\)\n    \);\n  \}\);"
memo_repl = """  const activeKPs = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      const msg = messages[i];
      if (msg.role === 'assistant' && msg.knowledge_points && msg.knowledge_points.length > 0) {
        return msg.knowledge_points;
      }
    }
    return [];
  }, [messages]);

  const recommendedResources = useMemo(() => {
    return resources.filter(res => {
      if (activeKPs.length === 0) return true; // Show all if no knowledge points mentioned yet
      return activeKPs.some(kp => 
        res.knowledge_point?.toLowerCase().includes(kp.toLowerCase()) ||
        res.title?.toLowerCase().includes(kp.toLowerCase())
      );
    });
  }, [resources, activeKPs]);"""
content = re.sub(memo_pattern, memo_repl, content)

# 5. Replace inline textarea onChange
textarea_pattern = r"                  onChange=\{e => \{\n                    setInputValue\(e\.target\.value\);\n                    e\.target\.style\.height = 'auto';\n                    e\.target\.style\.height = Math\.min\(e\.target\.scrollHeight, 128\) \+ 'px';\n                  \}\}"
textarea_repl = """                  onChange={handleTextareaChange}"""
content = re.sub(textarea_pattern, textarea_repl, content)

with open('src/pages/AIChat.jsx', 'w', encoding='utf-8') as f:
    f.write(content)

