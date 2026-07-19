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
