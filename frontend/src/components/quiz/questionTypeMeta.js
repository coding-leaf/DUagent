export const getQuestionTypeLabel = (type) => {
  const normalized = String(type || '').toLowerCase();
  if (normalized === 'single_choice') return '单选题';
  if (normalized === 'multi_choice' || normalized === 'multiple_choice') return '多选题';
  if (normalized === 'code') return '编程题';
  return '未知题型';
};
