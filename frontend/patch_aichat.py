import re

with open('src/pages/AIChat.jsx', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace 1: Top section imports to activeCourseName
pattern1 = r"import \{ useState, useEffect, useRef \} from 'react';.*?const activeCourseName = activeCourse\?\.name \|\| activeCourse\?\.title \|\| '未选择课程';"
repl1 = """import { useState, useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import { learningService } from '../api/services/learning';
import { useCourse } from '../context/CourseContext';
import { useChat } from '../context/ChatContext';
import Navbar from '../components/Navbar';
import ChatMessage from '../components/chat/ChatMessage';
import ChatEmptyState from '../components/chat/ChatEmptyState';
import { extractModelText } from '../utils/chatContent';
import Icon from '../components/Icon';

export default function AIChat() {
  const { activeCourseId, courses } = useCourse();
  
  // Replace massive local state with context hook
  const {
    sessions, activeSession, setActiveSession,
    messages, isSending,
    sendMessage, regenerate, editMessage, cancelStream, resetConversation, deleteSession
  } = useChat();

  const [inputValue, setInputValue] = useState('');
  const [resources, setResources] = useState([]);
  
  // Collapse & Drawer States
  const [leftCollapsed, setLeftCollapsed] = useState(false);
  const [rightCollapsed, setRightCollapsed] = useState(false);
  const [leftDrawerOpen, setLeftDrawerOpen] = useState(false);
  const [rightDrawerOpen, setRightDrawerOpen] = useState(false);
  
  const messagesEndRef = useRef(null);
  const [editingMsg, setEditingMsg] = useState(null);

  const activeCourse = courses?.find(c => c.id === activeCourseId);
  const activeCourseName = activeCourse?.name || activeCourse?.title || '未选择课程';"""
content = re.sub(pattern1, repl1, content, flags=re.DOTALL)

# Replace 2: useEffects to handleEditSubmit
pattern2 = r"  // Sync sessions list when course changes.*?    abortControllerRef\.current = chatService\.streamChat\([\s\S]*?    \);\n  \};"
repl2 = """  useEffect(() => {
    if (activeCourseId) {
      learningService.getResources({ course_id: activeCourseId, page: 1, page_size: 100 })
        .then(res => {
          if (res.code === 200 && res.data) {
            setResources(Array.isArray(res.data.resources || res.data) ? (res.data.resources || res.data) : []);
          }
        })
        .catch(console.error);
    } else {
      setTimeout(() => setResources([]), 0);
    }
  }, [activeCourseId]);

  // Handle auto-scroll down for incoming chunked text.
  useEffect(() => {
    // Note: Can cause layout thrashing on fast streams. Throttle wrapper advised later.
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Simplify handlers
  const handleResetConversation = () => {
    resetConversation();
    setLeftDrawerOpen(false);
  };

  const handleSendMessage = (overrideText = '') => {
    const textToSend = (overrideText || inputValue).trim();
    if (!textToSend || isSending || !activeCourseId) return;
    if (!overrideText) setInputValue('');
    sendMessage(textToSend);
  };

  const handleRegenerate = () => regenerate();

  const handleEditSubmit = (newContent) => {
    editMessage(newContent);
    setEditingMsg(null);
  };

  const handleDeleteSession = (id) => {
    deleteSession(id);
  };"""
content = re.sub(pattern2, repl2, content, flags=re.DOTALL)

# Replace 3: abortController logic in onClick setActiveSession
pattern3 = r"                      onClick=\{\(\) => \{\n                        if \(abortControllerRef\.current\) \{\n                          abortControllerRef\.current\(\);\n                          abortControllerRef\.current = null;\n                        \}\n                        setActiveSession\(session\.id\);\n                        setLeftDrawerOpen\(false\);\n                      \}\}"
repl3 = """                      onClick={() => {
                        setActiveSession(session.id);
                        setLeftDrawerOpen(false);
                      }}"""
content = re.sub(pattern3, repl3, content, flags=re.DOTALL)

# Replace 4: inline deleteSession JSX
pattern4 = r"                      onClick=\{async \(e\) => \{\n                        e\.stopPropagation\(\);\n                        if \(\!window\.confirm\('确定删除该对话？删除后不可恢复。'\)\) return;\n                        try \{\n                          await chatService\.deleteSession\(session\.id\);\n                          setSessions\(prev => prev\.filter\(s => s\.id \!\=\= session\.id\)\);\n                          if \(activeSession \=\=\= session\.id\) \{\n                            setActiveSession\(null\);\n                            setMessages\(\[\]\);\n                          \}\n                        \} catch \(err\) \{\n                          console\.error\('删除对话失败:', err\);\n                        \}\n                      \}\}"
repl4 = """                      onClick={(e) => {
                        e.stopPropagation();
                        if (!window.confirm('确定删除该对话？删除后不可恢复。')) return;
                        handleDeleteSession(session.id);
                      }}"""
content = re.sub(pattern4, repl4, content, flags=re.DOTALL)

# Replace 5: Stop generating button
pattern5 = r"                    <button\n                      onClick=\{\(\) => \{\n                        abortControllerRef\.current\?\.\(\);\n                        abortControllerRef\.current = null;\n                        setIsSending\(false\);\n                      \}\}\n                      className=\"w-8 h-8 rounded-lg bg-red-500 text-white flex items-center justify-center cursor-pointer hover:bg-red-600 active:scale-95 transition-all shadow-sm\""
repl5 = """                    <button
                      onClick={() => cancelStream()}
                      className="w-8 h-8 rounded-lg bg-red-500 text-white flex items-center justify-center cursor-pointer hover:bg-red-600 active:scale-95 transition-all shadow-sm\""""
content = re.sub(pattern5, repl5, content, flags=re.DOTALL)

with open('src/pages/AIChat.jsx', 'w', encoding='utf-8') as f:
    f.write(content)

