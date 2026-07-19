export const getErrorMessage = (error, fallback = '请求失败') => {
  const detail = error?.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (detail?.message) return detail.message;
  return error?.response?.data?.message || error?.message || fallback;
};
