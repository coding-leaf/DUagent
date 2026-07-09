import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import Icon from '../Icon';

export default function NodeResourcePanel({ activeCourseId, selectedNodeId, nodeResources, resourcesLoading }) {
  const [showFullExercises, setShowFullExercises] = useState(false);
  const [showAllTutorials, setShowAllTutorials] = useState(false);
  const [showAllExercises, setShowAllExercises] = useState(false);
  const [showAllMaterials, setShowAllMaterials] = useState(false);

  // Reset expansion states when node changes
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setShowFullExercises(false);
     
    setShowAllTutorials(false);
     
    setShowAllExercises(false);
     
    setShowAllMaterials(false);
  }, [selectedNodeId]);

  if (!selectedNodeId) return null;

  return (
    <section className="mt-8 space-y-6">
      <h3 className="font-h3 text-h3 flex items-center gap-2">
        <Icon name="library_books" className="material-symbols-outlined text-cyan-600"/>
        当前节点资源
        {nodeResources?.node_name && (
          <span className="text-body-md text-secondary font-normal">— {nodeResources.node_name}</span>
        )}
      </h3>

      {resourcesLoading ? (
        <div className="flex justify-center py-12">
          <Icon name="progress_activity" className="material-symbols-outlined animate-spin text-4xl text-cyan-500"/>
        </div>
      ) : nodeResources ? (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* 1. 薄弱点讲解 */}
          <div className="bg-white rounded-xl border border-gray-100 p-6 shadow-sm">
            <div className="flex items-center gap-2 mb-4">
              <div className="p-2 bg-orange-50 rounded-lg text-orange-600">
                <Icon name="lightbulb" className="material-symbols-outlined"/>
              </div>
              <h4 className="font-bold text-on-surface">薄弱点讲解</h4>
            </div>
            {nodeResources.weak_point_tutorials?.length > 0 ? (
              <div className="space-y-3 max-h-80 overflow-y-auto">
                {(showAllTutorials ? nodeResources.weak_point_tutorials : nodeResources.weak_point_tutorials.slice(0, 5)).map((item, i) => (
                  <div key={i} className="p-3 bg-slate-50 rounded-lg border border-gray-100">
                    <p className="text-sm font-bold text-on-surface mb-1">{item.title}</p>
                    <p className="text-xs text-secondary line-clamp-2 mb-2">{item.content || ''}</p>
                    {item.id ? (
                      <Link to={`/resource/${item.id}`} state={{ node: { id: selectedNodeId, name: nodeResources.node_name } }} className="text-xs text-cyan-600 hover:text-cyan-700 font-medium flex items-center gap-1">
                        查看资源 <Icon name="arrow_forward" className="material-symbols-outlined text-xs"/>
                      </Link>
                    ) : (
                      <span className="text-xs text-gray-400">暂无详情</span>
                    )}
                  </div>
                ))}
                {nodeResources.weak_point_tutorials.length > 5 && (
                  <button onClick={() => setShowAllTutorials(!showAllTutorials)}
                    className="text-xs text-cyan-600 hover:text-cyan-700 font-medium w-full text-center py-1">
                    {showAllTutorials ? '收起' : `展开全部 (${nodeResources.weak_point_tutorials.length} 条)`}
                  </button>
                )}
              </div>
            ) : (
              <p className="text-xs text-gray-400 py-4 text-center">该节点暂无薄弱点讲解</p>
            )}
          </div>

          {/* 2. 节点练习 */}
          <div className="bg-white rounded-xl border border-gray-100 p-6 shadow-sm">
            <div className="flex items-center gap-2 mb-4">
              <div className="p-2 bg-cyan-50 rounded-lg text-cyan-600">
                <Icon name="quiz" className="material-symbols-outlined"/>
              </div>
              <h4 className="font-bold text-on-surface">节点练习</h4>
            </div>
            {nodeResources.exercises?.length > 0 ? (
              <div className="space-y-3 max-h-80 overflow-y-auto">
                {(showAllExercises ? nodeResources.exercises : nodeResources.exercises.slice(0, 5)).map((item, i) => (
                  <div key={i} className="p-3 bg-slate-50 rounded-lg border border-gray-100">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="px-1.5 py-0.5 bg-cyan-100 text-cyan-700 text-[10px] rounded font-bold">
                        {item.type === 'single_choice' ? '单选' : item.type === 'multi_choice' ? '多选' : item.type}
                      </span>
                    </div>
                    <p className="text-xs text-secondary line-clamp-2">{item.content || ''}</p>
                  </div>
                ))}
                {nodeResources.exercises.length > 5 && (
                  <button onClick={() => setShowAllExercises(!showAllExercises)}
                    className="text-xs text-cyan-600 hover:text-cyan-700 font-medium w-full text-center py-1">
                    {showAllExercises ? '收起' : `展开全部 (${nodeResources.exercises.length} 条)`}
                  </button>
                )}
                <Link to={`/quiz?course_id=${activeCourseId}&node_id=${selectedNodeId}`} className="w-full block text-center py-2 bg-cyan-600 text-white rounded-lg text-sm font-bold hover:bg-cyan-700 transition-colors cursor-pointer">
                  进入练习
                </Link>
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center h-48 border border-dashed border-slate-200 rounded-xl bg-slate-50/50 p-4">
                <p className="text-xs text-slate-400 text-center">该节点暂无练习</p>
              </div>
            )}
          </div>

          {/* 3. 章节资料 */}
          <div className="bg-white rounded-xl border border-gray-100 p-6 shadow-sm">
            <div className="flex items-center gap-2 mb-4">
              <div className="p-2 bg-emerald-50 rounded-lg text-emerald-600">
                <Icon name="menu_book" className="material-symbols-outlined"/>
              </div>
              <h4 className="font-bold text-on-surface">章节资料</h4>
            </div>
            {nodeResources.chapter_materials?.length > 0 ? (
              <div className="space-y-3 max-h-80 overflow-y-auto">
                {(showAllMaterials ? nodeResources.chapter_materials : nodeResources.chapter_materials.slice(0, 5)).map((item, i) => (
                  <div key={i} className="p-3 bg-slate-50 rounded-lg border border-gray-100">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="px-1.5 py-0.5 bg-emerald-100 text-emerald-700 text-[10px] rounded font-bold">
                        {item.type || '资料'}
                      </span>
                      <p className="text-sm font-bold text-on-surface">{item.title}</p>
                    </div>
                    {item.id ? (
                      <Link to={`/resource/${item.id}`} state={{ node: { id: selectedNodeId, name: nodeResources.node_name } }} className="text-xs text-cyan-600 hover:text-cyan-700 font-medium flex items-center gap-1 mt-1">
                        查看资源 <Icon name="arrow_forward" className="material-symbols-outlined text-xs"/>
                      </Link>
                    ) : (
                      <span className="text-xs text-gray-400">暂无详情</span>
                    )}
                  </div>
                ))}
                {nodeResources.chapter_materials.length > 5 && (
                  <button onClick={() => setShowAllMaterials(!showAllMaterials)}
                    className="text-xs text-cyan-600 hover:text-cyan-700 font-medium w-full text-center py-1">
                    {showAllMaterials ? '收起' : `展开全部 (${nodeResources.chapter_materials.length} 条)`}
                  </button>
                )}
              </div>
            ) : (
              <p className="text-xs text-gray-400 py-4 text-center">该节点暂无章节资料</p>
            )}
          </div>
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-gray-100 p-8 text-center">
          <p className="text-sm text-gray-400">无法加载节点资源</p>
        </div>
      )}

      {/* 4. 全部练习集（折叠） */}
      {nodeResources?.full_exercise_set?.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-100 p-6 shadow-sm">
          <button
            onClick={() => setShowFullExercises(!showFullExercises)}
            className="w-full flex items-center justify-between"
          >
            <div className="flex items-center gap-2">
              <div className="p-2 bg-purple-50 rounded-lg text-purple-600">
                <Icon name="list_alt" className="material-symbols-outlined"/>
              </div>
              <h4 className="font-bold text-on-surface text-left">
                全部练习集
                <span className="text-xs text-secondary font-normal ml-2">共 {nodeResources.full_exercise_count || nodeResources.full_exercise_set?.length || 0} 题</span>
              </h4>
            </div>
            <Icon name="expand_more" className={`material-symbols-outlined text-gray-400 transition-transform ${showFullExercises ? 'rotate-180' : ''}`}/>
          </button>
          {showFullExercises && (
            <div className="mt-4 space-y-2 max-h-96 overflow-y-auto">
              {nodeResources.full_exercise_set.slice(0, 10).map((item, i) => (
                <div key={i} className="p-3 bg-slate-50 rounded-lg border border-gray-100">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="px-1.5 py-0.5 bg-purple-100 text-purple-700 text-[10px] rounded font-bold">
                      {item.type === 'single_choice' ? '单选' : item.type === 'multi_choice' ? '多选' : item.type}
                    </span>
                  </div>
                  <p className="text-xs text-secondary line-clamp-2">{item.content || ''}</p>
                </div>
              ))}
              {nodeResources.full_exercise_set.length > 10 && (
                <p className="text-xs text-gray-400 text-center pt-2">查看更多请进入练习</p>
              )}
            </div>
          )}
        </div>
      )}
    </section>
  );
}
