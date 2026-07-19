export function getApiErrorMessage(error, fallback = '请求失败') {
  const data = error?.response?.data;
  if (!data) {
    return error?.message || fallback;
  }

  if (typeof data.message === 'string' && data.message.trim()) {
    return data.message;
  }

  const detail = data.detail;
  if (typeof detail?.message === 'string' && detail.message.trim()) {
    return detail.message;
  }
  if (Array.isArray(detail)) {
    const firstMessage = detail
      .map((item) => formatValidationError(item))
      .find((message) => message);
    if (firstMessage) {
      return firstMessage;
    }
  }
  if (typeof detail === 'string' && detail.trim()) {
    return detail;
  }

  return fallback;
}

const fieldLabels = {
  username: '用户名',
  password: '密码',
  email: '电子邮箱',
  registration_code: '邀请码',
  captcha_token: '验证码标识',
  captcha_code: '验证码',
  real_name: '真实姓名',
  student_id: '学号 / 工号',
  major: '专业',
  grade: '年级',
  guidance_level: '引导粒度',
};

function formatValidationError(item) {
  if (!item || typeof item !== 'object') {
    return '';
  }

  const field = Array.isArray(item.loc) ? item.loc[item.loc.length - 1] : '';
  const label = fieldLabels[field] || field || '字段';
  const message = typeof item.msg === 'string' ? item.msg : '';
  const context = item.ctx || {};

  if (item.type === 'string_too_short' || message.includes('at least')) {
    const minLength = context.min_length;
    return minLength ? `${label}至少 ${minLength} 个字符` : `${label}长度过短`;
  }
  if (item.type === 'string_too_long' || message.includes('at most')) {
    const maxLength = context.max_length;
    return maxLength ? `${label}最多 ${maxLength} 个字符` : `${label}长度过长`;
  }
  if (message) {
    return `${label}: ${message}`;
  }
  return '';
}
