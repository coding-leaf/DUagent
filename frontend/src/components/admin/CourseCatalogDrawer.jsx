import { useCatalog } from '../../hooks/useCatalog';
import CatalogDrawerHeader from './catalog/CatalogDrawerHeader';
import CatalogSummaryStats from './catalog/CatalogSummaryStats';
import KnowledgeGraphSection from './catalog/KnowledgeGraphSection';
import MaterialUploadSection from './catalog/MaterialUploadSection';
import MaterialList from './catalog/MaterialList';
import ResourceGenerationSection from './catalog/ResourceGenerationSection';
import QuizGenerationSection from './catalog/QuizGenerationSection';
import GeneratedResourceList from './catalog/GeneratedResourceList';
import IngestionSection from './catalog/IngestionSection';

export default function CourseCatalogDrawer({ catalog, open, onClose, onChanged }) {
  const {
    materials, resources, knowledgeStatus, knowledgeGraphStatus,
    loading, error,
    uploadQueue, uploading,
    ingesting, activeTask, taskError,
    generationForm, generating, generationTask, generationTaskError,
    generationProcessing,
    knowledgeGraphGenerating, knowledgeGraphTask, knowledgeGraphTaskError,
    quizGenerating, quizGenTask, quizGenTaskError,
    deletingMaterialIds, deletingResourceIds,
    uploadDisabled, startDisabled, generationDisabled,
    materialDeleteDisabled, resourceDeleteDisabled, knowledgeGraphGenerationDisabled,
    hasReadyKnowledge, hasActiveKnowledgeGraph, hasExplicitResourceTarget,
    summary, taskProcessing, knowledgeGraphProcessing,
    handleUpload, handleStartIngestion,
    handleGenerationFieldChange, handleGenerationTypeToggle,
    handleStartKnowledgeGraphGeneration, handleStartGeneration,
    handleStartQuizGeneration, handleDeleteMaterial, handleDeleteResource,
  } = useCatalog({ catalog, open, onChanged });

  if (!open || !catalog) return null;

  return (
    <div data-testid="catalog-drawer" className="fixed inset-0 z-50 flex justify-end bg-slate-900/35">
      <button
        type="button"
        aria-label="关闭资源库详情"
        className="absolute inset-0 cursor-default"
        onClick={onClose}
      />
      <aside className="relative flex h-full w-full max-w-[560px] flex-col bg-white shadow-2xl">
        <CatalogDrawerHeader
          catalog={catalog}
          knowledgeStatus={knowledgeStatus}
          onClose={onClose}
        />

        <div className="flex-1 overflow-y-auto px-6 py-5">
          {error && (
            <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          )}

          <CatalogSummaryStats summary={summary} />

          <KnowledgeGraphSection
            knowledgeGraphStatus={knowledgeGraphStatus}
            knowledgeGraphTask={knowledgeGraphTask}
            knowledgeGraphTaskError={knowledgeGraphTaskError}
            knowledgeGraphProcessing={knowledgeGraphProcessing}
            knowledgeGraphGenerating={knowledgeGraphGenerating}
            knowledgeGraphGenerationDisabled={knowledgeGraphGenerationDisabled}
            onStartKnowledgeGraphGeneration={handleStartKnowledgeGraphGeneration}
          />

          <MaterialUploadSection
            uploadQueue={uploadQueue}
            uploading={uploading}
            uploadDisabled={uploadDisabled}
            onUpload={handleUpload}
          />

          <MaterialList
            materials={materials}
            loading={loading}
            materialDeleteDisabled={materialDeleteDisabled}
            deletingMaterialIds={deletingMaterialIds}
            onDeleteMaterial={handleDeleteMaterial}
          />

          <ResourceGenerationSection
            generationForm={generationForm}
            generationTask={generationTask}
            generationTaskError={generationTaskError}
            generationProcessing={generationProcessing}
            generating={generating}
            generationDisabled={generationDisabled}
            hasReadyKnowledge={hasReadyKnowledge}
            hasActiveKnowledgeGraph={hasActiveKnowledgeGraph}
            hasExplicitResourceTarget={hasExplicitResourceTarget}
            onStartGeneration={handleStartGeneration}
            onFieldChange={handleGenerationFieldChange}
            onTypeToggle={handleGenerationTypeToggle}
          />

          <QuizGenerationSection
            quizGenTask={quizGenTask}
            quizGenerating={quizGenerating}
            quizGenTaskError={quizGenTaskError}
            hasReadyKnowledge={hasReadyKnowledge}
            hasActiveKnowledgeGraph={hasActiveKnowledgeGraph}
            onStartQuizGeneration={handleStartQuizGeneration}
          />

          <GeneratedResourceList
            resources={resources}
            loading={loading}
            resourceDeleteDisabled={resourceDeleteDisabled}
            deletingResourceIds={deletingResourceIds}
            onDeleteResource={handleDeleteResource}
          />

          <IngestionSection
            knowledgeStatus={knowledgeStatus}
            activeTask={activeTask}
            taskError={taskError}
            taskProcessing={taskProcessing}
            ingesting={ingesting}
            startDisabled={startDisabled}
            onStartIngestion={handleStartIngestion}
          />
        </div>
      </aside>
    </div>
  );
}
