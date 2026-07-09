# Learning Effects Summary UI Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the "Learning Effect Summary" (学习效果总结) display across student and teacher dashboards from a raw text paragraph to a modern, structured two-column layout by parsing section contents client-side.

**Architecture:** Create a `summaryParser.js` utility that extracts structured sections (Scope, Mastery, Behavior, Suggestions) using standard header markers. Feed the parsed sections into a restructured two-column `EffectsSummaryCard` (Student dashboard) and compact layout (Teacher dashboard).

**Tech Stack:** React 19, Tailwind CSS, Lucide icons, Vitest.

---

## Proposed Changes

### Task 1: Create summaryParser utility and its tests

**Files:**
- Create: `frontend/src/utils/summaryParser.js`
- Create: `frontend/src/utils/__tests__/summaryParser.test.js`

- [ ] **Step 1: Write the failing unit tests**
  Create `frontend/src/utils/__tests__/summaryParser.test.js`:
  ```javascript
  import { describe, it, expect } from 'vitest';
  import { parseSummaryText } from '../summaryParser';

  describe('parseSummaryText', () => {
    it('should return null for null or empty input', () => {
      expect(parseSummaryText(null)).toBeNull();
      expect(parseSummaryText('')).toBeNull();
    });

    it('should split raw summary text into four distinct sections', () => {
      const sampleText = 
        "学习范围：目前正在学习C语言课程，已覆盖变量与作用域。当前掌握：目前尚未有知识点达到掌握状态。学习行为：学习时间非常有限，总学习时长仅28秒。下一步建议：1）优先集中复习3个薄弱知识点；2）逐步完成待练习节点；3）利用视频辅助理解。";
      
      const result = parseSummaryText(sampleText);
      
      expect(result).not.toBeNull();
      expect(result.scope).toBe("目前正在学习C语言课程，已覆盖变量与作用域。");
      expect(result.mastery).toBe("目前尚未有知识点达到掌握状态。");
      expect(result.behavior).toBe("学习时间非常有限，总学习时长仅28秒。");
      expect(result.suggestions).toHaveLength(3);
      expect(result.suggestions[0]).toEqual({
        id: 1,
        title: "优先集中复习3个薄弱知识点",
        desc: ""
      });
    });

    it('should parse suggestion title and description using punctuation delimiters', () => {
      const sampleText = 
        "下一步建议：鉴于您为大一新生，建议：1、优先复习：通过专项练习巩固基础。2、每天固定学习：培养连续学习习惯。";
      const result = parseSummaryText(sampleText);
      
      expect(result.suggestionsPrefix).toBe("鉴于您为大一新生，建议：");
      expect(result.suggestions).toHaveLength(2);
      expect(result.suggestions[0].title).toBe("优先复习");
      expect(result.suggestions[0].desc).toBe("通过专项练习巩固基础。");
      expect(result.suggestions[1].title).toBe("每天固定学习");
      expect(result.suggestions[1].desc).toBe("培养连续学习习惯。");
    });
  });
  ```

- [ ] **Step 2: Run test to verify it fails**
  Run: `cd frontend && npm run test:unit utils/__tests__/summaryParser.test.js`
  Expected: FAIL (Cannot find module '../summaryParser')

- [ ] **Step 3: Implement parser logic**
  Create `frontend/src/utils/summaryParser.js`:
  ```javascript
  /**
   * Parses the raw evaluation summary text into structured sections.
   * Expected sections: 学习范围、当前掌握、学习行为、下一步建议.
   */
  export function parseSummaryText(text) {
    if (!text) return null;

    const markers = [
      { key: 'scope', marker: '学习范围：' },
      { key: 'mastery', marker: '当前掌握：' },
      { key: 'behavior', marker: '学习行为：' },
      { key: 'suggestions', marker: '下一步建议：' }
    ];

    const found = markers
      .map(m => ({ ...m, index: text.indexOf(m.marker) }))
      .filter(m => m.index !== -1)
      .sort((a, b) => a.index - b.index);

    if (found.length === 0) {
      return { scope: text, mastery: '', behavior: '', suggestions: [], suggestionsPrefix: '' };
    }

    const result = {
      scope: '',
      mastery: '',
      behavior: '',
      suggestions: [],
      suggestionsPrefix: ''
    };

    for (let i = 0; i < found.length; i++) {
      const current = found[i];
      const next = found[i + 1];
      const startPos = current.index + current.marker.length;
      const endPos = next ? next.index : text.length;
      const content = text.substring(startPos, endPos).trim();

      if (current.key === 'suggestions') {
        const itemRegex = /(?:\d+[\)\）\、\.])\s*/g;
        const parts = content.split(itemRegex);
        
        const items = [];
        let prefix = '';
        if (parts[0] && parts[0].trim()) {
          prefix = parts[0].trim();
        }
        
        for (let j = 1; j < parts.length; j++) {
          const itemContent = parts[j].trim();
          if (itemContent) {
            let title = '';
            let desc = itemContent;
            
            // Check first for custom colons
            const colonIdx = itemContent.indexOf('：');
            const colonEnIdx = itemContent.indexOf(':');
            const finalColonIdx = colonIdx !== -1 ? colonIdx : colonEnIdx;
            
            if (finalColonIdx !== -1 && finalColonIdx < 20) {
              title = itemContent.substring(0, finalColonIdx).trim();
              desc = itemContent.substring(finalColonIdx + 1).trim();
            } else {
              // fallback split by comma or parentheses
              const splitIdx = itemContent.search(/[，（(,]/);
              if (splitIdx !== -1 && splitIdx < 20) {
                title = itemContent.substring(0, splitIdx).trim();
                desc = itemContent.substring(splitIdx).trim();
                if (desc.startsWith('，') || desc.startsWith(',') || desc.startsWith('；') || desc.startsWith(';')) {
                  desc = desc.substring(1).trim();
                }
              } else {
                title = itemContent;
                desc = '';
              }
            }
            
            items.push({
              id: j,
              title,
              desc
            });
          }
        }
        
        if (items.length === 0) {
          items.push({
            id: 1,
            title: '推荐学习建议',
            desc: content
          });
        }
        
        result.suggestions = items;
        result.suggestionsPrefix = prefix;
      } else {
        result[current.key] = content;
      }
    }

    return result;
  }
  ```

- [ ] **Step 4: Run test to verify it passes**
  Run: `cd frontend && npm run test:unit utils/__tests__/summaryParser.test.js`
  Expected: PASS

- [ ] **Step 5: Commit**
  Run:
  ```bash
  git add frontend/src/utils/summaryParser.js frontend/src/utils/__tests__/summaryParser.test.js
  git commit -m "feat: add summaryParser utility and unit tests"
  ```

---

### Task 2: Refactor EffectsSummaryCard to use two-column layout

**Files:**
- Modify: `frontend/src/components/effects/EffectsSummaryCard.jsx`

- [ ] **Step 1: Replace implementation in EffectsSummaryCard.jsx**
  Modify `frontend/src/components/effects/EffectsSummaryCard.jsx`:
  ```javascript
  import Icon from '../Icon';
  import { parseSummaryText } from '../../utils/summaryParser';

  export default function EffectsSummaryCard({ summaryText, loading }) {
    const parsed = parseSummaryText(summaryText);

    return (
      <div className="bg-white/80 backdrop-blur-md rounded-xl p-6 shadow-sm border border-gray-100 h-full flex flex-col justify-start">
        <h3 className="font-h3 text-xl font-bold mb-4 flex items-center border-b border-slate-100 pb-3">
          <Icon name="psychology" className="material-symbols-outlined mr-2 text-cyan-600"/>
          学习效果总结
        </h3>
        
        {loading ? (
          <p className="font-body-md text-slate-500 leading-relaxed">正在加载学习效果...</p>
        ) : parsed ? (
          <div className="flex flex-col md:flex-row gap-6">
            {/* Left Column: Diagnostics */}
            <div className="flex-1 md:flex-[1.4] space-y-4">
              {parsed.scope && (
                <div className="p-4 bg-cyan-50/50 border border-cyan-100 rounded-lg">
                  <h4 className="font-bold text-sm text-cyan-800 flex items-center mb-1">
                    <Icon name="menu_book" className="material-symbols-outlined text-base mr-1.5" />
                    学习范围
                  </h4>
                  <p className="text-sm text-slate-600 leading-relaxed">{parsed.scope}</p>
                </div>
              )}

              {parsed.mastery && (
                <div className="p-4 bg-red-50/50 border border-red-100 rounded-lg">
                  <h4 className="font-bold text-sm text-red-800 flex items-center mb-1">
                    <Icon name="analytics" className="material-symbols-outlined text-base mr-1.5" />
                    当前掌握
                  </h4>
                  <p className="text-sm text-slate-600 leading-relaxed">{parsed.mastery}</p>
                </div>
              )}

              {parsed.behavior && (
                <div className="p-4 bg-slate-50/80 border border-slate-100 rounded-lg">
                  <h4 className="font-bold text-sm text-slate-700 flex items-center mb-1">
                    <Icon name="insights" className="material-symbols-outlined text-base mr-1.5" />
                    学习行为
                  </h4>
                  <p className="text-sm text-slate-600 leading-relaxed">{parsed.behavior}</p>
                </div>
              )}
            </div>

            {/* Right Column: Recommendations */}
            {parsed.suggestions && parsed.suggestions.length > 0 && (
              <div className="flex-1 bg-slate-50/40 border border-dashed border-slate-200 rounded-xl p-5">
                <h4 className="font-bold text-base text-emerald-800 flex items-center mb-3">
                  <Icon name="check_circle" className="material-symbols-outlined text-emerald-600 mr-2" />
                  下一步学习建议
                </h4>
                
                {parsed.suggestionsPrefix && (
                  <p className="text-xs text-slate-400 mb-3">{parsed.suggestionsPrefix}</p>
                )}

                <div className="space-y-3">
                  {parsed.suggestions.map((item, idx) => (
                    <div key={idx} className="bg-white border border-gray-100 rounded-lg p-3 shadow-sm hover:shadow-md transition-shadow">
                      <div className="flex gap-2.5 items-start">
                        <span className="flex items-center justify-center w-5 h-5 bg-emerald-100 text-emerald-800 rounded-full text-xs font-bold flex-shrink-0 mt-0.5">
                          {idx + 1}
                        </span>
                        <div>
                          <div className="text-sm font-bold text-slate-800 mb-1">{item.title}</div>
                          {item.desc && (
                            <div className="text-xs text-slate-500 leading-relaxed">{item.desc}</div>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : (
          <p className="font-body-md text-slate-500 leading-relaxed">
            暂无学习效果总结。完成节点练习或点击重新评估后，系统会基于真实学习记录生成总结。
          </p>
        )}
      </div>
    );
  }
  ```

- [ ] **Step 2: Build the project to confirm compilation**
  Run: `cd frontend && npm run build`
  Expected: Success without TypeScript or asset errors.

- [ ] **Step 3: Commit**
  Run:
  ```bash
  git add frontend/src/components/effects/EffectsSummaryCard.jsx
  git commit -m "feat: optimize EffectsSummaryCard with two-column parsed content layout"
  ```

---

### Task 3: Refactor TeacherStudentReport to display parsed summary layout

**Files:**
- Modify: `frontend/src/pages/TeacherStudentReport.jsx`

- [ ] **Step 1: Replace raw evaluation summary panel in TeacherStudentReport.jsx**
  Modify `frontend/src/pages/TeacherStudentReport.jsx` to parse and show a compact summary view:
  ```javascript
  // Add this import near line 7
  import { parseSummaryText } from '../utils/summaryParser';
  ```
  And replace lines 88-93:
  ```javascript
  {report.evaluation_summary?.summary_text && (() => {
    const parsed = parseSummaryText(report.evaluation_summary.summary_text);
    return (
      <div className="bg-white border border-slate-100 rounded-xl p-5 shadow-sm">
        <div className="font-bold text-sm text-cyan-600 flex items-center mb-3">
          <Icon name="psychology" className="material-symbols-outlined mr-1.5" />
          AI 深度学情诊断与教学建议
        </div>
        
        {parsed ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Left Column: Diagnostics Summary */}
            <div className="space-y-3">
              {parsed.scope && (
                <div className="p-3 bg-slate-50/50 border border-slate-100 rounded-lg text-xs">
                  <div className="font-bold text-slate-700 flex items-center mb-1">
                    <Icon name="school" className="material-symbols-outlined text-sm mr-1" />
                    学生学习状态
                  </div>
                  <p className="text-slate-600 leading-relaxed">{parsed.scope}</p>
                </div>
              )}
              
              {parsed.mastery && (
                <div className="p-3 bg-red-50/50 border border-red-100 rounded-lg text-xs">
                  <div className="font-bold text-red-800 flex items-center mb-1">
                    <Icon name="error_outline" className="material-symbols-outlined text-sm mr-1" />
                    关键薄弱环节 (优先介入)
                  </div>
                  <p className="text-slate-600 leading-relaxed">{parsed.mastery}</p>
                </div>
              )}
            </div>

            {/* Right Column: Teaching recommendations Checklist */}
            {parsed.suggestions && parsed.suggestions.length > 0 && (
              <div className="p-3 bg-emerald-50/30 border border-emerald-100 rounded-lg">
                <div className="font-bold text-xs text-emerald-800 flex items-center mb-2">
                  <Icon name="check_circle_outline" className="material-symbols-outlined text-sm mr-1" />
                  针对性教学引导建议
                </div>
                <div className="space-y-2 text-xs">
                  {parsed.suggestions.map((item, idx) => (
                    <div key={idx} className="bg-white border border-slate-100 rounded p-2 flex gap-2">
                      <div className="w-4 h-4 rounded-full bg-emerald-100 text-emerald-800 flex items-center justify-center font-bold text-[9px] flex-shrink-0 mt-0.5">
                        {idx + 1}
                      </div>
                      <div>
                        <span className="font-bold text-slate-800">{item.title}：</span>
                        <span className="text-slate-500">{item.desc || '结合相关要点展开。'}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : (
          <p className="text-sm text-slate-500">{report.evaluation_summary.summary_text}</p>
        )}
      </div>
    );
  })()}
  ```

- [ ] **Step 2: Run build and lint to verify complete frontend compilation**
  Run:
  ```bash
  cd frontend && npm run lint && npm run build
  ```
  Expected: Compilation passes, no errors found.

- [ ] **Step 3: Commit**
  Run:
  ```bash
  git add frontend/src/pages/TeacherStudentReport.jsx
  git commit -m "feat: refactor TeacherStudentReport AI summary section with parsed compact layout"
  ```
