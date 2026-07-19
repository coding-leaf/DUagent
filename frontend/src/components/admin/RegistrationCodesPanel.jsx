import { useState, useEffect, useCallback } from 'react';
import { adminService } from '../../api/services/admin';
import { getErrorMessage } from '../../utils/apiError';
import Icon from '../Icon';

import { formatDateTime } from '../../utils/date';

export default function RegistrationCodesPanel() {
  const [regCodes, setRegCodes] = useState([]);
  const [loadingRegCodes, setLoadingRegCodes] = useState(false);
  const [regCodeError, setRegCodeError] = useState('');
  const [generatingRole, setGeneratingRole] = useState(null);
  const [revokingCodeId, setRevokingCodeId] = useState(null);
  const [copiedCodeId, setCopiedCodeId] = useState(null);

  const fetchRegCodes = useCallback(async () => {
    setLoadingRegCodes(true);
    setRegCodeError('');
    try {
      const res = await adminService.getRegistrationCodes();
      if (res.code === 200) setRegCodes(res.data?.codes || []);
    } catch (e) {
      setRegCodeError(getErrorMessage(e, '注册码加载失败'));
    } finally {
      setLoadingRegCodes(false);
    }
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => {
      fetchRegCodes();
    }, 0);
    return () => clearTimeout(timer);
  }, [fetchRegCodes]);

  const handleGenerateCode = async (role) => {
    setGeneratingRole(role);
    setRegCodeError('');
    try {
      const res = await adminService.createRegistrationCode(role);
      if (res.code === 201 || res.code === 200) {
        await fetchRegCodes();
      } else {
        setRegCodeError(res.message || '生成失败');
      }
    } catch (e) {
      setRegCodeError(getErrorMessage(e, '生成失败'));
    } finally {
      setGeneratingRole(null);
    }
  };

  const handleRevokeCode = async (codeId) => {
    if (!window.confirm('确认吊销该注册码？吊销后无法用于注册。')) return;
    setRevokingCodeId(codeId);
    setRegCodeError('');
    try {
      const res = await adminService.revokeRegistrationCode(codeId);
      if (res.code === 200) {
        await fetchRegCodes();
      } else {
        setRegCodeError(res.message || '吊销失败');
      }
    } catch (e) {
      setRegCodeError(getErrorMessage(e, '吊销失败'));
    } finally {
      setRevokingCodeId(null);
    }
  };

  const handleCopyCode = (c) => {
    navigator.clipboard.writeText(c.code).then(() => {
      setCopiedCodeId(c.id);
      setTimeout(() => setCopiedCodeId(null), 1500);
    });
  };

  return (
    <div className="animate-in fade-in duration-500">
      <div className="flex justify-between items-end mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 mb-1">注册码管理</h1>
          <p className="text-sm text-slate-500">生成注册码分发给用户，用于注册时验证身份和角色。</p>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => handleGenerateCode('teacher')}
            disabled={generatingRole === 'teacher'}
            className="inline-flex items-center gap-1.5 rounded-lg bg-amber-500 px-4 py-2 text-sm font-medium text-white hover:bg-amber-600 disabled:opacity-60 disabled:cursor-not-allowed transition-colors cursor-pointer"
          >
            <Icon name="add" className="material-symbols-outlined text-[18px]"/>
            {generatingRole === 'teacher' ? '生成中…' : '生成教师码'}
          </button>
          <button
            type="button"
            onClick={() => handleGenerateCode('student')}
            disabled={generatingRole === 'student'}
            className="inline-flex items-center gap-1.5 rounded-lg bg-cyan-600 px-4 py-2 text-sm font-medium text-white hover:bg-cyan-700 disabled:opacity-60 disabled:cursor-not-allowed transition-colors cursor-pointer"
          >
            <Icon name="add" className="material-symbols-outlined text-[18px]"/>
            {generatingRole === 'student' ? '生成中…' : '生成学生码'}
          </button>
          <button onClick={fetchRegCodes} className="flex items-center gap-1 text-cyan-600 hover:underline text-sm font-medium cursor-pointer">
            <Icon name="refresh" className="material-symbols-outlined text-[18px]"/>
          </button>
        </div>
      </div>
      {regCodeError && <p className="text-sm text-red-500 mb-4">{regCodeError}</p>}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-slate-500 text-xs uppercase tracking-wider">
            <tr>
              <th className="px-6 py-4 font-medium text-left">注册码</th>
              <th className="px-6 py-4 font-medium text-left">角色</th>
              <th className="px-6 py-4 font-medium text-left">生成时间</th>
              <th className="px-6 py-4 font-medium text-right">操作</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {loadingRegCodes ? (
              <tr><td colSpan="4" className="text-center py-12 text-slate-400">加载中…</td></tr>
            ) : regCodes.length === 0 ? (
              <tr><td colSpan="4" className="text-center py-12 text-slate-400">暂无注册码，点击右上角按钮生成</td></tr>
            ) : (
              regCodes.map((c) => (
                <tr key={c.id} className="hover:bg-slate-50/50 transition-colors">
                  <td className="px-6 py-4 font-mono font-bold text-slate-800 tracking-wider">{c.code}</td>
                  <td className="px-6 py-4">
                    <span className={`px-2.5 py-1 rounded text-xs font-bold ${
                      c.role === 'teacher' ? 'bg-amber-100 text-amber-700' : 'bg-cyan-100 text-cyan-700'
                    }`}>{c.role === 'teacher' ? '教师' : '学生'}</span>
                  </td>
                  <td className="px-6 py-4 text-slate-500 text-xs">{formatDateTime(c.create_time)}</td>
                  <td className="px-6 py-4 text-right">
                    <div className="flex items-center justify-end gap-2">
                      <button
                        type="button"
                        onClick={() => handleCopyCode(c)}
                        className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-50 transition-colors cursor-pointer"
                      >
                        <Icon name={copiedCodeId === c.id ? 'check' : 'content_copy'} className="material-symbols-outlined text-[16px]"/>
                        {copiedCodeId === c.id ? '已复制' : '复制'}
                      </button>
                      <button
                        type="button"
                        onClick={() => handleRevokeCode(c.id)}
                        disabled={revokingCodeId === c.id}
                        className="inline-flex items-center gap-1 rounded-lg border border-red-200 bg-white px-3 py-1.5 text-xs font-medium text-red-600 hover:bg-red-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors cursor-pointer"
                      >
                        <Icon name="block" className="material-symbols-outlined text-[16px]"/>
                        {revokingCodeId === c.id ? '吊销中' : '吊销'}
                      </button>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
