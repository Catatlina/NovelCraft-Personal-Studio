/**
 * Generation Console page - V7 Sprint 2
 * 
 * Visualizes the chapter generation pipeline with real-time progress.
 */
import { useState } from 'react';
import {
  Play, Pause, RotateCcw, Settings, Sparkles,
  Brain, Target, Wand2, Shield, CheckCircle,
  Clock, ChevronRight, Zap,
} from 'lucide-react';
import brainApi from '../api/client';

interface GenerationConsoleProps {
  novelId: string;
}

interface PipelineStep {
  id: string;
  name: string;
  description: string;
  icon: any;
  status: 'pending' | 'running' | 'completed' | 'error';
  duration?: number;
}

const PIPELINE_STEPS: PipelineStep[] = [
  { id: 'planning', name: 'Planning', description: 'Plan chapter structure and goals', icon: Target, status: 'pending' },
  { id: 'context', name: 'Context Assembly', description: 'Assemble story context from brain', icon: Brain, status: 'pending' },
  { id: 'scene', name: 'Scene Direction', description: 'Plan scene beats and pacing', icon: Settings, status: 'pending' },
  { id: 'generation', name: 'AI Generation', description: 'Generate chapter text', icon: Wand2, status: 'pending' },
  { id: 'deai', name: 'De-AI Processing', description: 'Remove AI-generated feel', icon: Sparkles, status: 'pending' },
  { id: 'review', name: 'Quality Review', description: '7-dimensional quality check', icon: Shield, status: 'pending' },
  { id: 'memory', name: 'Memory Update', description: 'Extract and store new memories', icon: Brain, status: 'pending' },
];

export function GenerationConsole({ novelId }: GenerationConsoleProps) {
  const [steps, setSteps] = useState<PipelineStep[]>(PIPELINE_STEPS);
  const [isGenerating, setIsGenerating] = useState(false);
  const [currentStep, setCurrentStep] = useState<string | null>(null);
  const [chapterNumber, setChapterNumber] = useState(1);
  const [prompt, setPrompt] = useState('');
  const [generationResult, setGenerationResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  const handleGenerate = async () => {
    setIsGenerating(true);
    setError(null);
    setGenerationResult(null);

    // Reset steps（点击生成后进入等待真实结果的状态，不再模拟）
    const resetSteps = PIPELINE_STEPS.map(s => ({ ...s, status: 'pending' as const }));
    setSteps(resetSteps);

    try {
      // 真实调用后端 director 生成接口；不做假进度条、不伪造结果
      const result = await brainApi.generateChapter(novelId, {
        chapter_number: chapterNumber,
        prompt: prompt || undefined,
      });
      setGenerationResult(result || null);
      // 有真实步骤信息时同步到管线展示
      const stepNames = result?.steps_executed || [];
      const visibleAliases: Record<string, string[]> = {
        planning: ['plan'],
        context: ['perceive'],
        scene: ['plan'],
        generation: ['execute'],
        deai: ['execute'],
        review: ['observe'],
        memory: ['update'],
      };
      if (Array.isArray(stepNames) && stepNames.length) {
        setSteps(prev => prev.map(s => ({
          ...s,
          // Backend reports logical agent-loop steps; map them to the visible
          // console without inventing intermediate progress.
          status: (visibleAliases[s.id] || []).some(name => stepNames.includes(name))
            ? ('completed' as const) : s.status,
        })));
      }
    } catch (err: any) {
      // 失败如实报错，不伪造 mock 结果
      setError(err?.message || '生成失败');
    } finally {
      setCurrentStep(null);
      setIsGenerating(false);
    }
  };

  const handleReset = () => {
    setSteps(PIPELINE_STEPS.map(s => ({ ...s, status: 'pending' as const })));
    setCurrentStep(null);
    setGenerationResult(null);
    setError(null);
  };

  const getStepColor = (status: string) => {
    switch (status) {
      case 'completed': return 'text-green-600 bg-green-50 border-green-200';
      case 'running': return 'text-blue-600 bg-blue-50 border-blue-200';
      case 'error': return 'text-red-600 bg-red-50 border-red-200';
      default: return 'text-gray-400 bg-gray-50 border-gray-200';
    }
  };

  const getStepIcon = (status: string, Icon: any) => {
    if (status === 'completed') return CheckCircle;
    return Icon;
  };

  const completedSteps = steps.filter(s => s.status === 'completed').length;
  const progress = (completedSteps / steps.length) * 100;

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Sparkles className="h-7 w-7 text-purple-600" />
            Generation Console
          </h1>
          <p className="text-gray-500 mt-1">
            Visualize and control the chapter generation pipeline
          </p>
        </div>
        <div className="flex gap-3">
          <button
            onClick={handleReset}
            disabled={isGenerating}
            className="px-4 py-2 text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50 flex items-center gap-2"
          >
            <RotateCcw className="h-4 w-4" />
            Reset
          </button>
          <button
            onClick={handleGenerate}
            disabled={isGenerating}
            className="px-6 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 flex items-center gap-2"
          >
            {isGenerating ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white" />
                Generating...
              </>
            ) : (
              <>
                <Play className="h-4 w-4" />
                Generate Chapter
              </>
            )}
          </button>
        </div>
      </div>

      {/* Input Section */}
      <div className="bg-white rounded-lg border border-gray-200 p-5 shadow-sm">
        <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
          <Settings className="h-5 w-5 text-gray-600" />
          Generation Settings
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Chapter Number
            </label>
            <input
              type="number"
              min="1"
              value={chapterNumber}
              onChange={(e) => setChapterNumber(parseInt(e.target.value))}
              disabled={isGenerating}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-purple-500 disabled:bg-gray-50"
            />
          </div>
          <div className="md:col-span-2">
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Prompt / Outline (optional)
            </label>
            <input
              type="text"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              disabled={isGenerating}
              placeholder="Enter a prompt or outline for this chapter..."
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-purple-500 disabled:bg-gray-50"
            />
          </div>
        </div>
      </div>

      {/* Progress Bar */}
      <div className="bg-white rounded-lg border border-gray-200 p-5 shadow-sm">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
            <Zap className="h-5 w-5 text-amber-500" />
            Pipeline Progress
          </h2>
          <span className="text-sm text-gray-500">
            {completedSteps} / {steps.length} steps
          </span>
        </div>
        <div className="w-full bg-gray-200 rounded-full h-3">
          <div
            className="bg-gradient-to-r from-purple-500 to-blue-500 h-3 rounded-full transition-all duration-500"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      {/* Pipeline Steps */}
      <div className="bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden">
        <div className="p-5 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-900">Generation Pipeline</h2>
        </div>
        <div className="divide-y divide-gray-100">
          {steps.map((step, index) => {
            const StepIcon = getStepIcon(step.status, step.icon);
            const isActive = currentStep === step.id;
            const isLast = index === steps.length - 1;
            
            return (
              <div
                key={step.id}
                className={`p-4 transition-colors ${
                  isActive ? 'bg-blue-50' : 'hover:bg-gray-50'
                }`}
              >
                <div className="flex items-center gap-4">
                  {/* Step number / connector */}
                  <div className="flex flex-col items-center">
                    <div className={`w-10 h-10 rounded-full flex items-center justify-center border-2 ${getStepColor(step.status)}`}>
                      <StepIcon className="h-5 w-5" />
                    </div>
                    {!isLast && (
                      <div className={`w-0.5 h-8 ${
                        step.status === 'completed' ? 'bg-green-400' : 'bg-gray-200'
                      }`} />
                    )}
                  </div>

                  {/* Step info */}
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <h3 className={`font-medium ${
                        step.status === 'completed' ? 'text-gray-900' :
                        step.status === 'running' ? 'text-blue-700' :
                        'text-gray-500'
                      }`}>
                        {step.name}
                      </h3>
                      {step.status === 'running' && (
                        <span className="px-2 py-0.5 text-xs font-medium rounded-full bg-blue-100 text-blue-700 flex items-center gap-1">
                          <div className="animate-pulse w-2 h-2 bg-blue-500 rounded-full" />
                          Running
                        </span>
                      )}
                      {step.status === 'completed' && (
                        <span className="px-2 py-0.5 text-xs font-medium rounded-full bg-green-100 text-green-700">
                          {step.duration?.toFixed(1)}s
                        </span>
                      )}
                    </div>
                    <p className="text-sm text-gray-500 mt-0.5">
                      {step.description}
                    </p>
                  </div>

                  {/* Arrow */}
                  {!isLast && (
                    <ChevronRight className={`h-5 w-5 ${
                      step.status === 'completed' ? 'text-green-400' : 'text-gray-300'
                    }`} />
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Result */}
      {generationResult && (
        <div className="bg-white rounded-lg border border-gray-200 p-5 shadow-sm">
          <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <CheckCircle className="h-5 w-5 text-green-600" />
            Generation Complete
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="p-4 bg-gray-50 rounded-lg text-center">
              <p className="text-2xl font-bold text-gray-900">
                {generationResult.chapter_number}
              </p>
              <p className="text-sm text-gray-500">Chapter</p>
            </div>
            <div className="p-4 bg-gray-50 rounded-lg text-center">
              <p className="text-2xl font-bold text-gray-900">
                {generationResult.word_count?.toLocaleString() || '-'}
              </p>
              <p className="text-sm text-gray-500">Words</p>
            </div>
            <div className="p-4 bg-gray-50 rounded-lg text-center">
              {(() => {
                const gatePassed = generationResult.passed_review === true
                  && generationResult.quality_gate?.passed === true;
                return (
                  <>
                    <p className={`text-2xl font-bold ${
                      gatePassed && generationResult.review_score >= 80 ? 'text-green-600' :
                      generationResult.review_score >= 60 ? 'text-amber-600' :
                      'text-red-600'
                    }`}>
                      {generationResult.review_score || '-'}
                    </p>
                    <p className="text-sm text-gray-500">V7 审阅分（非交付状态）</p>
                    <p className={`mt-1 text-xs font-medium ${gatePassed ? 'text-green-600' : 'text-red-600'}`}>
                      {gatePassed ? '质量门通过，可交付' : '质量门未通过，需重写'}
                    </p>
                  </>
                );
              })()}
            </div>
            <div className="p-4 bg-gray-50 rounded-lg text-center">
              <p className="text-sm font-mono text-gray-600 truncate">
                {generationResult.run_id?.slice(0, 8) || '-'}...
              </p>
              <p className="text-sm text-gray-500">Run ID</p>
            </div>
          </div>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <p className="text-red-700 font-medium">Generation failed</p>
          <p className="text-red-600 text-sm mt-1">{error}</p>
        </div>
      )}
    </div>
  );
}

export default GenerationConsole;
