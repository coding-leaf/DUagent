import useSWR from 'swr';

import { personalizedResourcesService } from '../api/services/personalizedResources';

export default function usePersonalizedResources(courseId, sourceType = 'all') {
  const key = courseId ? ['personalized-resources', courseId, sourceType] : null;
  const { data, error, isLoading, mutate } = useSWR(
    key,
    async ([, id, source]) => {
      const params = source === 'all' ? {} : { source_type: source };
      const response = await personalizedResourcesService.list(id, params);
      return response.data;
    },
    {
      refreshInterval: (latest) => latest?.processing_count > 0 ? 3000 : 0,
      revalidateOnFocus: true,
    },
  );

  const remove = async (id) => {
    await personalizedResourcesService.delete(id);
    await mutate();
  };

  return {
    items: data?.items || [],
    total: data?.total || 0,
    processingCount: data?.processing_count || 0,
    isLoading,
    error,
    refresh: mutate,
    remove,
  };
}
