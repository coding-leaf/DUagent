import useSWR from 'swr';
import { learningService } from '../api/services/learning';
import { fetcherWrapper } from '../utils/fetcher';

export function useResourceDetail(id) {
  const { data: res, error, isLoading, mutate } = useSWR(
    id ? ['resourceDetail', id] : null,
    () => fetcherWrapper(learningService.getResourceDetail(id))
  );

  return {
    resource: res?.data || null,
    loading: isLoading,
    error,
    mutate
  };
}
