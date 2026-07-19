export const fetcherWrapper = async (promise) => {
  const res = await promise;
  if (res.code !== 200 && res.code !== 202) {
    throw new Error(res.message || '请求失败');
  }
  return res;
};
