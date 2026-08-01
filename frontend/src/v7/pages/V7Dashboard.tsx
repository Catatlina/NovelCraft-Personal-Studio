/**
 * V7 Dashboard - Main entry point for V7 features.
 * 
 * Includes sidebar navigation and page routing.
 */
import { useState } from 'react';
import {
  Brain, Database, Target, Shield, GitBranch, Activity,
  Settings, ChevronLeft, ChevronRight, Sparkles,
  Wand2, Scale, Zap, DollarSign, FileCode,
} from 'lucide-react';
import BrainOverview from './BrainOverview';
import StateManager from './StateManager';
import GoalManager from './GoalManager';
import ConstraintManager from './ConstraintManager';
import VersionManager from './VersionManager';
import EventLog from './EventLog';
import GenerationConsole from './GenerationConsole';
import TraceViewer from './TraceViewer';
import DecisionLog from './DecisionLog';
import CostMonitor from './CostMonitor';
import PromptManager from './PromptManager';

interface V7DashboardProps {
  novelId: string;
}

type PageKey = 
  | 'overview' 
  | 'states' 
  | 'goals' 
  | 'constraints' 
  | 'versions' 
  | 'events' 
  | 'generation'
  | 'trace'
  | 'decisions'
  | 'cost'
  | 'prompts'
  | 'config';

const NAV_ITEMS: { key: PageKey; label: string; icon: any; badge?: string; section?: string }[] = [
  // Brain section
  { key: 'overview', label: 'Overview', icon: Brain, section: 'Brain' },
  { key: 'states', label: 'States', icon: Database, badge: 'Brain' },
  { key: 'goals', label: 'Goals', icon: Target },
  { key: 'constraints', label: 'Constraints', icon: Shield },
  { key: 'versions', label: 'Versions', icon: GitBranch },
  { key: 'events', label: 'Event Log', icon: Activity },
  // Generation section
  { key: 'generation', label: 'Generation', icon: Wand2, badge: 'New', section: 'Generation' },
  { key: 'trace', label: 'Trace Viewer', icon: Zap },
  { key: 'decisions', label: 'Decisions', icon: Scale },
  // Engineering section
  { key: 'cost', label: 'Cost Monitor', icon: DollarSign, badge: 'New', section: 'Engineering' },
  { key: 'prompts', label: 'Prompts', icon: FileCode, badge: 'New' },
  { key: 'config', label: 'Config', icon: Settings, badge: 'Soon' },
];

export function V7Dashboard({ novelId }: V7DashboardProps) {
  const [currentPage, setCurrentPage] = useState<PageKey>('overview');
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  const renderPage = () => {
    switch (currentPage) {
      case 'overview':
        return <BrainOverview novelId={novelId} />;
      case 'states':
        return <StateManager novelId={novelId} />;
      case 'goals':
        return <GoalManager novelId={novelId} />;
      case 'constraints':
        return <ConstraintManager novelId={novelId} />;
      case 'versions':
        return <VersionManager novelId={novelId} />;
      case 'events':
        return <EventLog novelId={novelId} />;
      case 'generation':
        return <GenerationConsole novelId={novelId} />;
      case 'trace':
        return <TraceViewer novelId={novelId} />;
      case 'decisions':
        return <DecisionLog novelId={novelId} />;
      case 'cost':
        return <CostMonitor novelId={novelId} />;
      case 'prompts':
        return <PromptManager novelId={novelId} />;
      case 'config':
        return (
          <div className="p-6">
            <div className="text-center py-12">
              <Settings className="mx-auto h-12 w-12 text-gray-300 mb-4" />
              <h2 className="text-xl font-semibold text-gray-900">Configuration</h2>
              <p className="text-gray-500 mt-2">
                System configuration page coming soon
              </p>
              <p className="text-sm text-gray-400 mt-1">
                Decision permissions, model routing, and more
              </p>
            </div>
          </div>
        );
      default:
        return null;
    }
  };

  // Group items by section
  const sections: { name: string; items: typeof NAV_ITEMS }[] = [];
  let currentSection: { name: string; items: typeof NAV_ITEMS } | null = null;
  
  NAV_ITEMS.forEach(item => {
    if (item.section) {
      currentSection = { name: item.section, items: [] };
      sections.push(currentSection);
    }
    if (currentSection) {
      currentSection.items.push(item);
    }
  });

  return (
    <div className="flex h-full bg-gray-50">
      {/* Sidebar */}
      <div
        className={`${
          sidebarCollapsed ? 'w-16' : 'w-64'
        } bg-white border-r border-gray-200 flex flex-col transition-all duration-200`}
      >
        {/* Logo / Header */}
        <div className="p-4 border-b border-gray-200 flex items-center justify-between">
          {!sidebarCollapsed && (
            <div className="flex items-center gap-2">
              <div className="p-1.5 bg-gradient-to-br from-blue-500 to-purple-600 rounded-lg">
                <Sparkles className="h-5 w-5 text-white" />
              </div>
              <div>
                <h1 className="text-sm font-bold text-gray-900">Starlume AI</h1>
                <p className="text-xs text-gray-500">V7 Alpha</p>
              </div>
            </div>
          )}
          <button
            onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
            className="p-1 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded"
          >
            {sidebarCollapsed ? (
              <ChevronRight className="h-4 w-4" />
            ) : (
              <ChevronLeft className="h-4 w-4" />
            )}
          </button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 p-2 space-y-1 overflow-y-auto">
          {sections.map((section, sectionIndex) => (
            <div key={section.name} className={sectionIndex > 0 ? 'mt-4' : ''}>
              {!sidebarCollapsed && (
                <p className="px-3 py-2 text-xs font-semibold text-gray-400 uppercase tracking-wider">
                  {section.name}
                </p>
              )}
              {section.items.map((item) => {
                const Icon = item.icon;
                const isActive = currentPage === item.key;
                return (
                  <button
                    key={item.key}
                    onClick={() => setCurrentPage(item.key)}
                    className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                      isActive
                        ? 'bg-blue-50 text-blue-600'
                        : 'text-gray-700 hover:bg-gray-50 hover:text-gray-900'
                    }`}
                    title={sidebarCollapsed ? item.label : undefined}
                  >
                    <Icon className={`h-5 w-5 flex-shrink-0 ${
                      isActive ? 'text-blue-600' : 'text-gray-400'
                    }`} />
                    {!sidebarCollapsed && (
                      <>
                        <span className="flex-1 text-left">{item.label}</span>
                        {item.badge && (
                          <span className={`px-1.5 py-0.5 text-xs rounded-full ${
                            item.badge === 'Soon'
                              ? 'bg-gray-100 text-gray-500'
                              : item.badge === 'New'
                              ? 'bg-green-100 text-green-600'
                              : 'bg-blue-100 text-blue-600'
                          }`}>
                            {item.badge}
                          </span>
                        )}
                      </>
                    )}
                  </button>
                );
              })}
            </div>
          ))}
        </nav>

        {/* Footer */}
        {!sidebarCollapsed && (
          <div className="p-4 border-t border-gray-200">
            <div className="p-3 bg-gradient-to-br from-blue-50 to-purple-50 rounded-lg">
              <p className="text-xs font-medium text-gray-700">
                Novel Intelligence System
              </p>
              <p className="text-xs text-gray-500 mt-1">
                Global state-driven AI writing
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Main Content */}
      <div className="flex-1 overflow-y-auto">
        {renderPage()}
      </div>
    </div>
  );
}

export default V7Dashboard;
