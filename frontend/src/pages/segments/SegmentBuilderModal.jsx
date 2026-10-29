import React, { useState, useEffect } from 'react';
import {
  X,
  Plus,
  Trash2,
  Users,
  Eye,
  CheckCircle2,
  XCircle,
  HelpCircle,
  AlertCircle,
  Layers,
  Sparkles,
  ArrowRight,
  ShieldAlert
} from 'lucide-react';
import {
  getSupportedFields,
  createSegment,
  updateSegment,
  previewRules
} from '../../services/segmentService';

const DEFAULT_FIELD_DEFINITIONS = {
  name: {
    label: 'Full Name',
    type: 'text',
    operators: ['equals', 'not_equals', 'contains', 'starts_with', 'is_empty', 'is_not_empty']
  },
  email: {
    label: 'Email Address',
    type: 'text',
    operators: ['equals', 'not_equals', 'contains', 'starts_with', 'is_empty', 'is_not_empty']
  },
  phone: {
    label: 'Phone Number',
    type: 'text',
    operators: ['equals', 'not_equals', 'contains', 'starts_with', 'is_empty', 'is_not_empty']
  },
  age: {
    label: 'Age',
    type: 'numeric',
    operators: ['equals', 'not_equals', 'greater_than', 'greater_than_or_equal', 'less_than', 'less_than_or_equal', 'is_empty', 'is_not_empty']
  },
  gender: {
    label: 'Gender',
    type: 'categorical',
    operators: ['equals', 'not_equals', 'in', 'is_empty', 'is_not_empty'],
    options: ['Male', 'Female', 'Non-binary', 'Other', 'Prefer not to say']
  },
  city: {
    label: 'City / District',
    type: 'text',
    operators: ['equals', 'not_equals', 'contains', 'starts_with', 'is_empty', 'is_not_empty']
  },
  state: {
    label: 'State / Region',
    type: 'text',
    operators: ['equals', 'not_equals', 'contains', 'starts_with', 'is_empty', 'is_not_empty']
  },
  preferred_language: {
    label: 'Preferred Language',
    type: 'categorical',
    operators: ['equals', 'not_equals', 'in', 'is_empty', 'is_not_empty'],
    options: [
      { code: 'hi', label: 'Hindi (hi)' },
      { code: 'en', label: 'English (en)' },
      { code: 'bn', label: 'Bengali (bn)' },
      { code: 'ta', label: 'Tamil (ta)' },
      { code: 'te', label: 'Telugu (te)' },
      { code: 'mr', label: 'Marathi (mr)' },
      { code: 'gu', label: 'Gujarati (gu)' },
      { code: 'kn', label: 'Kannada (kn)' },
      { code: 'ml', label: 'Malayalam (ml)' },
      { code: 'pa', label: 'Punjabi (pa)' },
      { code: 'or', label: 'Odia (or)' }
    ]
  },
  occupation: {
    label: 'Occupation',
    type: 'text',
    operators: ['equals', 'not_equals', 'contains', 'starts_with', 'is_empty', 'is_not_empty']
  },
  organization_department: {
    label: 'Organization / Department',
    type: 'text',
    operators: ['equals', 'not_equals', 'contains', 'starts_with', 'is_empty', 'is_not_empty']
  },
  preferred_channel: {
    label: 'Preferred Channel',
    type: 'categorical',
    operators: ['equals', 'not_equals', 'in', 'is_empty', 'is_not_empty'],
    options: [
      { code: 'email', label: 'Email' },
      { code: 'sms', label: 'SMS' },
      { code: 'whatsapp', label: 'WhatsApp' },
      { code: 'voice', label: 'Voice Call' }
    ]
  },
  consent_status: {
    label: 'Consent Status',
    type: 'consent',
    operators: ['equals', 'not_equals', 'is_empty', 'is_not_empty']
  }
};

const OPERATOR_LABELS = {
  equals: 'Equals (exact)',
  not_equals: 'Does not equal',
  contains: 'Contains',
  starts_with: 'Starts with',
  greater_than: 'Greater than (>)',
  greater_than_or_equal: 'Greater than or equal (>=)',
  less_than: 'Less than (<)',
  less_than_or_equal: 'Less than or equal (<=)',
  in: 'Is one of (comma-separated)',
  is_empty: 'Is empty / missing',
  is_not_empty: 'Is not empty / present'
};

export default function SegmentBuilderModal({
  isOpen,
  onClose,
  editingSegment = null,
  onSuccess
}) {
  const isEditing = Boolean(editingSegment);

  // Form State
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [rootConnector, setRootConnector] = useState('AND');
  const [conditions, setConditions] = useState([
    { field: 'preferred_language', operator: 'equals', value: 'hi' }
  ]);
  const [subGroups, setSubGroups] = useState([]);

  // Preview State
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewResult, setPreviewResult] = useState(null);
  const [previewError, setPreviewError] = useState('');

  // Submit State
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState('');

  // Load field metadata or fallback
  const [fieldDefs, setFieldDefs] = useState(DEFAULT_FIELD_DEFINITIONS);

  useEffect(() => {
    if (isOpen) {
      getSupportedFields()
        .then((data) => {
          if (data && data.fields) {
            // Merge with local options for categorical fields
            const merged = { ...DEFAULT_FIELD_DEFINITIONS };
            for (const [key, val] of Object.entries(data.fields)) {
              merged[key] = {
                ...merged[key],
                ...val
              };
            }
            setFieldDefs(merged);
          }
        })
        .catch(() => {
          // Keep defaults
        });
    }
  }, [isOpen]);

  // Reset or initialize state when opening modal
  useEffect(() => {
    if (isOpen) {
      setFormError('');
      setPreviewResult(null);
      setPreviewError('');

      if (editingSegment) {
        setName(editingSegment.name || '');
        setDescription(editingSegment.description || '');

        const rules = editingSegment.filter_rules || {};
        setRootConnector(rules.connector || 'AND');

        const initialConditions = (rules.conditions || []).map((c) => ({
          field: c.field,
          operator: c.operator,
          value: c.value === null || c.value === undefined ? '' : c.value
        }));
        setConditions(
          initialConditions.length > 0
            ? initialConditions
            : [{ field: 'preferred_language', operator: 'equals', value: 'hi' }]
        );

        const initialSubGroups = (rules.groups || []).map((g) => ({
          connector: g.connector || 'AND',
          conditions: (g.conditions || []).map((c) => ({
            field: c.field,
            operator: c.operator,
            value: c.value === null || c.value === undefined ? '' : c.value
          }))
        }));
        setSubGroups(initialSubGroups);
      } else {
        setName('');
        setDescription('');
        setRootConnector('AND');
        setConditions([
          { field: 'preferred_language', operator: 'equals', value: 'hi' }
        ]);
        setSubGroups([]);
      }
    }
  }, [isOpen, editingSegment]);

  if (!isOpen) return null;

  // Build clean filter_rules object
  const buildFilterRulesPayload = () => {
    const cleanConditions = conditions
      .filter((c) => c.field && c.operator)
      .map((c) => {
        const item = { field: c.field, operator: c.operator };
        if (c.operator !== 'is_empty' && c.operator !== 'is_not_empty') {
          // Normalize values
          if (c.field === 'age') {
            item.value = c.value === '' ? null : Number(c.value);
          } else if (c.field === 'consent_status') {
            if (c.value === 'true' || c.value === true) item.value = true;
            else if (c.value === 'false' || c.value === false) item.value = false;
            else item.value = null;
          } else if (c.operator === 'in') {
            if (Array.isArray(c.value)) {
              item.value = c.value;
            } else {
              item.value = String(c.value)
                .split(',')
                .map((v) => v.trim())
                .filter(Boolean);
            }
          } else {
            item.value = c.value;
          }
        }
        return item;
      });

    const cleanGroups = subGroups
      .map((g) => ({
        connector: g.connector || 'AND',
        conditions: (g.conditions || [])
          .filter((c) => c.field && c.operator)
          .map((c) => {
            const item = { field: c.field, operator: c.operator };
            if (c.operator !== 'is_empty' && c.operator !== 'is_not_empty') {
              if (c.field === 'age') {
                item.value = c.value === '' ? null : Number(c.value);
              } else if (c.field === 'consent_status') {
                if (c.value === 'true' || c.value === true) item.value = true;
                else if (c.value === 'false' || c.value === false) item.value = false;
                else item.value = null;
              } else if (c.operator === 'in') {
                if (Array.isArray(c.value)) {
                  item.value = c.value;
                } else {
                  item.value = String(c.value)
                    .split(',')
                    .map((v) => v.trim())
                    .filter(Boolean);
                }
              } else {
                item.value = c.value;
              }
            }
            return item;
          })
      }))
      .filter((g) => g.conditions.length > 0);

    return {
      connector: rootConnector,
      conditions: cleanConditions,
      ...(cleanGroups.length > 0 ? { groups: cleanGroups } : {})
    };
  };

  // Condition Handlers for Root Group
  const handleAddCondition = () => {
    if (conditions.length + subGroups.reduce((acc, g) => acc + g.conditions.length, 0) >= 20) {
      setFormError('Maximum limit of 20 total conditions reached.');
      return;
    }
    setConditions([
      ...conditions,
      { field: 'preferred_language', operator: 'equals', value: 'hi' }
    ]);
  };

  const handleUpdateCondition = (index, updates) => {
    const updated = [...conditions];
    const current = updated[index];
    const newField = updates.field !== undefined ? updates.field : current.field;

    // If field changed, set default operator and sensible default value
    if (updates.field && updates.field !== current.field) {
      const fieldDef = fieldDefs[newField] || DEFAULT_FIELD_DEFINITIONS[newField];
      const defaultOp = fieldDef?.operators?.[0] || 'equals';
      let defaultValue = '';
      if (newField === 'consent_status') defaultValue = true;
      else if (newField === 'preferred_language') defaultValue = 'hi';
      else if (newField === 'preferred_channel') defaultValue = 'email';
      else if (newField === 'age') defaultValue = 25;

      updated[index] = {
        field: newField,
        operator: defaultOp,
        value: defaultValue
      };
    } else {
      updated[index] = { ...current, ...updates };
    }
    setConditions(updated);
  };

  const handleRemoveCondition = (index) => {
    if (conditions.length <= 1 && subGroups.length === 0) {
      setFormError('At least one condition or group is required.');
      return;
    }
    setConditions(conditions.filter((_, idx) => idx !== index));
  };

  // Sub-Group Handlers
  const handleAddSubGroup = () => {
    if (subGroups.length >= 2) {
      setFormError('Maximum 2 sub-groups allowed to maintain predictable rule hierarchy.');
      return;
    }
    setSubGroups([
      ...subGroups,
      {
        connector: 'AND',
        conditions: [{ field: 'city', operator: 'equals', value: '' }]
      }
    ]);
  };

  const handleRemoveSubGroup = (groupIndex) => {
    setSubGroups(subGroups.filter((_, idx) => idx !== groupIndex));
  };

  const handleAddSubGroupCondition = (groupIndex) => {
    const updated = [...subGroups];
    updated[groupIndex].conditions.push({
      field: 'city',
      operator: 'equals',
      value: ''
    });
    setSubGroups(updated);
  };

  const handleUpdateSubGroupCondition = (groupIndex, conditionIndex, updates) => {
    const updated = [...subGroups];
    const current = updated[groupIndex].conditions[conditionIndex];
    const newField = updates.field !== undefined ? updates.field : current.field;

    if (updates.field && updates.field !== current.field) {
      const fieldDef = fieldDefs[newField] || DEFAULT_FIELD_DEFINITIONS[newField];
      const defaultOp = fieldDef?.operators?.[0] || 'equals';
      let defaultValue = '';
      if (newField === 'consent_status') defaultValue = true;
      else if (newField === 'preferred_language') defaultValue = 'hi';
      else if (newField === 'preferred_channel') defaultValue = 'email';
      else if (newField === 'age') defaultValue = 25;

      updated[groupIndex].conditions[conditionIndex] = {
        field: newField,
        operator: defaultOp,
        value: defaultValue
      };
    } else {
      updated[groupIndex].conditions[conditionIndex] = { ...current, ...updates };
    }
    setSubGroups(updated);
  };

  const handleRemoveSubGroupCondition = (groupIndex, conditionIndex) => {
    const updated = [...subGroups];
    updated[groupIndex].conditions = updated[groupIndex].conditions.filter(
      (_, idx) => idx !== conditionIndex
    );
    if (updated[groupIndex].conditions.length === 0) {
      // Remove group if empty
      setSubGroups(subGroups.filter((_, idx) => idx !== groupIndex));
    } else {
      setSubGroups(updated);
    }
  };

  // Preview Handler
  const handlePreview = async () => {
    setPreviewLoading(true);
    setPreviewError('');
    try {
      const filterRules = buildFilterRulesPayload();
      const result = await previewRules(filterRules, 5, 0);
      setPreviewResult(result);
    } catch (err) {
      setPreviewError(
        err.response?.data?.detail || err.message || 'Failed to preview rule matching.'
      );
    } finally {
      setPreviewLoading(false);
    }
  };

  // Submit Handler
  const handleSubmit = async (e) => {
    e.preventDefault();
    setFormError('');

    const trimmedName = name.trim();
    if (!trimmedName) {
      setFormError('Segment name is required.');
      return;
    }

    if (conditions.length === 0 && subGroups.length === 0) {
      setFormError('At least one condition is required.');
      return;
    }

    const filterRules = buildFilterRulesPayload();

    setSubmitting(true);
    try {
      if (isEditing) {
        await updateSegment(editingSegment.id, {
          name: trimmedName,
          description: description.trim() || null,
          filter_rules: filterRules
        });
        onSuccess(`Segment "${trimmedName}" was successfully updated.`);
      } else {
        await createSegment({
          name: trimmedName,
          description: description.trim() || null,
          filter_rules: filterRules
        });
        onSuccess(`Segment "${trimmedName}" was successfully created.`);
      }
      onClose();
    } catch (err) {
      const detail = err.response?.data?.detail;
      if (err.response?.status === 409) {
        setFormError('A segment with this name already exists. Please choose a distinct name.');
      } else if (err.response?.status === 403) {
        setFormError('You do not have permission to modify this segment.');
      } else if (typeof detail === 'string') {
        setFormError(detail);
      } else if (Array.isArray(detail)) {
        setFormError(detail.map((d) => d.msg || JSON.stringify(d)).join(', '));
      } else {
        setFormError(err.message || 'Failed to save segment.');
      }
    } finally {
      setSubmitting(false);
    }
  };

  // Helper to render value input per condition
  const renderValueInput = (cond, onChange) => {
    const fieldDef = fieldDefs[cond.field] || DEFAULT_FIELD_DEFINITIONS[cond.field];
    const isUnary = cond.operator === 'is_empty' || cond.operator === 'is_not_empty';

    if (isUnary) {
      return (
        <span className="text-xs text-slate-400 italic px-3 py-2 bg-slate-100 rounded-lg border border-slate-200">
          No value required
        </span>
      );
    }

    // Consent field
    if (cond.field === 'consent_status') {
      return (
        <select
          value={cond.value === null ? 'null' : String(cond.value)}
          onChange={(e) => {
            const val = e.target.value;
            onChange(val === 'true' ? true : val === 'false' ? false : null);
          }}
          className="px-3 py-2 text-xs rounded-lg border border-slate-300 bg-white font-medium focus:ring-2 focus:ring-brand-500 focus:outline-none"
        >
          <option value="true">Confirmed (true)</option>
          <option value="false">Revoked (false)</option>
          <option value="null">Unconfirmed (null)</option>
        </select>
      );
    }

    // Language options
    if (cond.field === 'preferred_language' && cond.operator !== 'in') {
      const options = fieldDef?.options || [];
      return (
        <select
          value={cond.value}
          onChange={(e) => onChange(e.target.value)}
          className="px-3 py-2 text-xs rounded-lg border border-slate-300 bg-white font-medium focus:ring-2 focus:ring-brand-500 focus:outline-none"
        >
          <option value="">Select language...</option>
          {options.map((opt) => (
            <option key={opt.code || opt} value={opt.code || opt}>
              {opt.label || opt}
            </option>
          ))}
        </select>
      );
    }

    // Channel options
    if (cond.field === 'preferred_channel' && cond.operator !== 'in') {
      const options = fieldDef?.options || [];
      return (
        <select
          value={cond.value}
          onChange={(e) => onChange(e.target.value)}
          className="px-3 py-2 text-xs rounded-lg border border-slate-300 bg-white font-medium focus:ring-2 focus:ring-brand-500 focus:outline-none"
        >
          <option value="">Select channel...</option>
          {options.map((opt) => (
            <option key={opt.code || opt} value={opt.code || opt}>
              {opt.label || opt}
            </option>
          ))}
        </select>
      );
    }

    // Gender options
    if (cond.field === 'gender' && cond.operator !== 'in') {
      const options = fieldDef?.options || ['Male', 'Female', 'Non-binary', 'Other', 'Prefer not to say'];
      return (
        <select
          value={cond.value}
          onChange={(e) => onChange(e.target.value)}
          className="px-3 py-2 text-xs rounded-lg border border-slate-300 bg-white font-medium focus:ring-2 focus:ring-brand-500 focus:outline-none"
        >
          <option value="">Select gender...</option>
          {options.map((opt) => (
            <option key={opt} value={opt}>
              {opt}
            </option>
          ))}
        </select>
      );
    }

    // Numeric age
    if (cond.field === 'age') {
      return (
        <input
          type="number"
          min="1"
          max="120"
          value={cond.value ?? ''}
          placeholder="e.g. 25"
          onChange={(e) => onChange(e.target.value)}
          className="px-3 py-2 text-xs rounded-lg border border-slate-300 bg-white focus:ring-2 focus:ring-brand-500 focus:outline-none w-28"
        />
      );
    }

    // IN operator
    if (cond.operator === 'in') {
      const valStr = Array.isArray(cond.value) ? cond.value.join(', ') : cond.value || '';
      return (
        <input
          type="text"
          value={valStr}
          placeholder="e.g. hi, en, ta (comma-separated)"
          onChange={(e) => onChange(e.target.value)}
          className="px-3 py-2 text-xs rounded-lg border border-slate-300 bg-white focus:ring-2 focus:ring-brand-500 focus:outline-none flex-1 min-w-[180px]"
        />
      );
    }

    // Default text input
    return (
      <input
        type="text"
        value={cond.value ?? ''}
        placeholder="Enter criteria value..."
        onChange={(e) => onChange(e.target.value)}
        className="px-3 py-2 text-xs rounded-lg border border-slate-300 bg-white focus:ring-2 focus:ring-brand-500 focus:outline-none flex-1 min-w-[180px]"
      />
    );
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="relative bg-white rounded-2xl max-w-4xl w-full shadow-2xl border border-slate-200 overflow-hidden flex flex-col max-h-[92vh]">
        
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between bg-slate-50">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-brand-100 text-brand-700 flex items-center justify-center">
              <Layers className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-slate-900">
                {isEditing ? `Edit Segment: ${editingSegment.name}` : 'Create Audience Segment'}
              </h3>
              <p className="text-xs text-slate-500">
                Build demographic and preference filters to dynamically target communication cohorts.
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-lg flex items-center justify-center text-slate-400 hover:text-slate-600 hover:bg-slate-200 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="flex-1 overflow-y-auto p-6 space-y-6">
          {formError && (
            <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-xs text-rose-700 flex items-center gap-2">
              <AlertCircle className="w-4 h-4 text-rose-600 flex-shrink-0" />
              <span>{formError}</span>
            </div>
          )}

          {/* Basic Info */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1">
                Segment Name <span className="text-rose-500">*</span>
              </label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Hindi Senior Citizens"
                required
                className="w-full px-3.5 py-2 text-sm rounded-xl border border-slate-300 focus:ring-2 focus:ring-brand-500 focus:border-brand-500 outline-none transition"
              />
            </div>
            <div>
              <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1">
                Description (Optional)
              </label>
              <input
                type="text"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="e.g. Target cohort for regional civic health advisories"
                className="w-full px-3.5 py-2 text-sm rounded-xl border border-slate-300 focus:ring-2 focus:ring-brand-500 focus:border-brand-500 outline-none transition"
              />
            </div>
          </div>

          {/* Rule Builder Card */}
          <div className="border border-slate-200 rounded-2xl p-5 bg-slate-50/50 space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-200">
              <div className="flex items-center gap-2">
                <span className="text-xs font-bold text-slate-800 uppercase tracking-wider">
                  Rule Logic Precedence:
                </span>
                <div className="inline-flex rounded-lg bg-slate-200 p-0.5 text-xs font-semibold">
                  <button
                    type="button"
                    onClick={() => setRootConnector('AND')}
                    className={`px-3 py-1 rounded-md transition ${
                      rootConnector === 'AND'
                        ? 'bg-white text-brand-700 shadow-sm font-bold'
                        : 'text-slate-600 hover:text-slate-900'
                    }`}
                  >
                    Match ALL (AND)
                  </button>
                  <button
                    type="button"
                    onClick={() => setRootConnector('OR')}
                    className={`px-3 py-1 rounded-md transition ${
                      rootConnector === 'OR'
                        ? 'bg-white text-brand-700 shadow-sm font-bold'
                        : 'text-slate-600 hover:text-slate-900'
                    }`}
                  >
                    Match ANY (OR)
                  </button>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={handleAddSubGroup}
                  disabled={subGroups.length >= 2}
                  className="px-3 py-1.5 text-xs font-semibold text-slate-700 bg-white hover:bg-slate-100 border border-slate-300 rounded-lg shadow-sm disabled:opacity-40 transition"
                  title="Add secondary rule grouping"
                >
                  + Add Sub-Group
                </button>
                <button
                  type="button"
                  onClick={handleAddCondition}
                  className="px-3 py-1.5 text-xs font-semibold text-white bg-brand-600 hover:bg-brand-700 rounded-lg shadow-sm transition flex items-center gap-1"
                >
                  <Plus className="w-3.5 h-3.5" />
                  Add Condition
                </button>
              </div>
            </div>

            {/* Root Conditions List */}
            <div className="space-y-3">
              {conditions.map((cond, index) => {
                const fieldDef = fieldDefs[cond.field] || DEFAULT_FIELD_DEFINITIONS[cond.field];
                const validOperators = fieldDef?.operators || ['equals', 'not_equals'];

                return (
                  <div
                    key={index}
                    className="flex flex-wrap items-center gap-2.5 p-3 bg-white rounded-xl border border-slate-200 shadow-sm"
                  >
                    {/* Index / Connector indicator */}
                    <span className="w-6 h-6 rounded-md bg-slate-100 text-slate-500 font-bold text-[10px] flex items-center justify-center">
                      {index === 0 ? '1' : rootConnector}
                    </span>

                    {/* Field select */}
                    <select
                      value={cond.field}
                      onChange={(e) => handleUpdateCondition(index, { field: e.target.value })}
                      className="px-3 py-2 text-xs rounded-lg border border-slate-300 bg-white font-medium focus:ring-2 focus:ring-brand-500 focus:outline-none"
                    >
                      {Object.entries(fieldDefs).map(([key, def]) => (
                        <option key={key} value={key}>
                          {def.label || key}
                        </option>
                      ))}
                    </select>

                    {/* Operator select */}
                    <select
                      value={cond.operator}
                      onChange={(e) => handleUpdateCondition(index, { operator: e.target.value })}
                      className="px-3 py-2 text-xs rounded-lg border border-slate-300 bg-white font-medium focus:ring-2 focus:ring-brand-500 focus:outline-none"
                    >
                      {validOperators.map((op) => (
                        <option key={op} value={op}>
                          {OPERATOR_LABELS[op] || op}
                        </option>
                      ))}
                    </select>

                    {/* Value Input */}
                    <div className="flex-1 flex items-center gap-2">
                      {renderValueInput(cond, (val) =>
                        handleUpdateCondition(index, { value: val })
                      )}
                    </div>

                    {/* Remove button */}
                    <button
                      type="button"
                      onClick={() => handleRemoveCondition(index)}
                      className="p-1.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition"
                      title="Remove condition"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                );
              })}
            </div>

            {/* Sub-Groups Render */}
            {subGroups.map((group, groupIdx) => (
              <div
                key={groupIdx}
                className="mt-4 p-4 rounded-xl border-2 border-dashed border-indigo-200 bg-indigo-50/40 space-y-3"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="text-[11px] font-bold text-indigo-900 uppercase">
                      Sub-Group #{groupIdx + 1} ({rootConnector} with parent)
                    </span>
                    <select
                      value={group.connector}
                      onChange={(e) => {
                        const updated = [...subGroups];
                        updated[groupIdx].connector = e.target.value;
                        setSubGroups(updated);
                      }}
                      className="px-2 py-1 text-xs rounded border border-indigo-300 bg-white font-semibold text-indigo-700"
                    >
                      <option value="AND">Sub-Match ALL (AND)</option>
                      <option value="OR">Sub-Match ANY (OR)</option>
                    </select>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => handleAddSubGroupCondition(groupIdx)}
                      className="text-xs font-semibold text-indigo-700 hover:text-indigo-900 hover:underline"
                    >
                      + Add Rule
                    </button>
                    <button
                      type="button"
                      onClick={() => handleRemoveSubGroup(groupIdx)}
                      className="text-xs font-semibold text-rose-600 hover:text-rose-800 hover:underline ml-3"
                    >
                      Remove Sub-Group
                    </button>
                  </div>
                </div>

                <div className="space-y-2">
                  {group.conditions.map((cond, condIdx) => {
                    const fieldDef = fieldDefs[cond.field] || DEFAULT_FIELD_DEFINITIONS[cond.field];
                    const validOperators = fieldDef?.operators || ['equals', 'not_equals'];

                    return (
                      <div
                        key={condIdx}
                        className="flex flex-wrap items-center gap-2 p-2.5 bg-white rounded-lg border border-indigo-100"
                      >
                        <span className="w-5 h-5 rounded bg-indigo-100 text-indigo-700 font-bold text-[9px] flex items-center justify-center">
                          {condIdx === 0 ? '•' : group.connector}
                        </span>

                        <select
                          value={cond.field}
                          onChange={(e) =>
                            handleUpdateSubGroupCondition(groupIdx, condIdx, { field: e.target.value })
                          }
                          className="px-2.5 py-1.5 text-xs rounded border border-slate-300 bg-white"
                        >
                          {Object.entries(fieldDefs).map(([key, def]) => (
                            <option key={key} value={key}>
                              {def.label || key}
                            </option>
                          ))}
                        </select>

                        <select
                          value={cond.operator}
                          onChange={(e) =>
                            handleUpdateSubGroupCondition(groupIdx, condIdx, { operator: e.target.value })
                          }
                          className="px-2.5 py-1.5 text-xs rounded border border-slate-300 bg-white"
                        >
                          {validOperators.map((op) => (
                            <option key={op} value={op}>
                              {OPERATOR_LABELS[op] || op}
                            </option>
                          ))}
                        </select>

                        <div className="flex-1 flex items-center gap-2">
                          {renderValueInput(cond, (val) =>
                            handleUpdateSubGroupCondition(groupIdx, condIdx, { value: val })
                          )}
                        </div>

                        <button
                          type="button"
                          onClick={() => handleRemoveSubGroupCondition(groupIdx, condIdx)}
                          className="p-1 text-slate-400 hover:text-rose-600 rounded"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>

          {/* Live Preview Section */}
          <div className="border border-slate-200 rounded-2xl p-5 bg-white space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Users className="w-4 h-4 text-brand-600" />
                <h4 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
                  Audience Qualification Preview
                </h4>
              </div>
              <button
                type="button"
                onClick={handlePreview}
                disabled={previewLoading}
                className="inline-flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-semibold text-brand-700 bg-brand-50 hover:bg-brand-100 border border-brand-200 rounded-lg transition"
              >
                <Eye className="w-3.5 h-3.5" />
                {previewLoading ? 'Evaluating Audience...' : 'Test & Preview Matching'}
              </button>
            </div>

            {previewError && (
              <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-xs text-rose-700">
                {previewError}
              </div>
            )}

            {previewResult && (
              <div className="space-y-3">
                <div className="flex items-center justify-between p-3 rounded-xl bg-slate-50 border border-slate-200">
                  <div className="flex items-center gap-2">
                    <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse" />
                    <span className="text-xs font-semibold text-slate-700">
                      Evaluated Audience Match:
                    </span>
                    <span className="text-sm font-extrabold text-slate-900">
                      {previewResult.total_matching.toLocaleString()} recipients
                    </span>
                  </div>
                  <span className="text-[11px] text-slate-500">
                    Live database query
                  </span>
                </div>

                {previewResult.sample_members?.length > 0 ? (
                  <div className="border border-slate-200 rounded-xl overflow-hidden">
                    <table className="w-full text-left text-xs">
                      <thead className="bg-slate-50 text-slate-600 font-semibold border-b border-slate-200">
                        <tr>
                          <th className="px-3 py-2">Name</th>
                          <th className="px-3 py-2">Lang</th>
                          <th className="px-3 py-2">Channel</th>
                          <th className="px-3 py-2">Location</th>
                          <th className="px-3 py-2">Consent</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100">
                        {previewResult.sample_members.map((m) => (
                          <tr key={m.id} className="hover:bg-slate-50">
                            <td className="px-3 py-1.5 font-medium text-slate-900">{m.name}</td>
                            <td className="px-3 py-1.5 uppercase font-semibold text-slate-700">{m.preferred_language || '—'}</td>
                            <td className="px-3 py-1.5 capitalize text-slate-600">{m.preferred_channel || '—'}</td>
                            <td className="px-3 py-1.5 text-slate-600">{m.city || m.state || '—'}</td>
                            <td className="px-3 py-1.5">
                              {m.consent_status === true ? (
                                <span className="text-[10px] text-emerald-700 font-medium">Confirmed</span>
                              ) : m.consent_status === false ? (
                                <span className="text-[10px] text-rose-700 font-medium">Revoked</span>
                              ) : (
                                <span className="text-[10px] text-amber-700 font-medium">Unconfirmed</span>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p className="text-xs text-slate-500 text-center py-4 bg-slate-50 rounded-xl border border-slate-200">
                    No recipients in the database currently match this condition combination.
                  </p>
                )}
              </div>
            )}
          </div>

          {/* Consent / Privacy Safe Notice */}
          <div className="flex items-start gap-2.5 p-3 rounded-xl bg-slate-100 text-slate-600 text-xs">
            <ShieldAlert className="w-4 h-4 text-slate-500 mt-0.5 flex-shrink-0" />
            <div>
              <span className="font-semibold text-slate-800">Compliance Assurance:</span> Creating or previewing segments does not trigger messages. Recipient consent verification occurs independently at message dispatch time during campaign execution.
            </div>
          </div>
        </form>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-slate-200 bg-slate-50 flex items-center justify-end gap-3">
          <button
            type="button"
            onClick={onClose}
            disabled={submitting}
            className="px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-200 border border-slate-300 rounded-lg transition"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleSubmit}
            disabled={submitting}
            className="px-5 py-2 text-xs font-semibold text-white bg-brand-600 hover:bg-brand-700 disabled:opacity-60 rounded-lg shadow-sm transition flex items-center gap-1.5"
          >
            {submitting ? 'Saving Segment...' : isEditing ? 'Save Changes' : 'Create Segment'}
          </button>
        </div>

      </div>
    </div>
  );
}

