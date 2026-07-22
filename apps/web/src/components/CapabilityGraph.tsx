import { useEffect, useRef, useState, useCallback } from 'react';
import { Graph } from '@antv/g6';
import { api } from '../api';
import type { CapabilityDetail } from '../types';

interface TreeNode {
  id: string;
  name: string;
  code?: string;
  capabilityId?: number;
  level: 'root' | 'direction' | 'category' | 'capability';
  children?: TreeNode[];
}

interface FlatCapability {
  id: number;
  name: string;
  code: string;
  categoryName: string;
  directionName: string;
}

export function CapabilityGraph() {
  const containerRef = useRef<HTMLDivElement>(null);
  const graphRef = useRef<Graph | null>(null);
  const [treeData, setTreeData] = useState<TreeNode | null>(null);
  const [flatCapabilities, setFlatCapabilities] = useState<FlatCapability[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCapability, setSelectedCapability] = useState<CapabilityDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);

  // Fetch tree data
  useEffect(() => {
    const fetchTree = async () => {
      try {
        const data = await api.getCapabilityTree();
        setTreeData(data);

        // Flatten capabilities for sidebar list
        const flat: FlatCapability[] = [];
        const traverse = (node: TreeNode, directionName: string, categoryName: string) => {
          if (node.level === 'capability' && node.capabilityId) {
            flat.push({
              id: node.capabilityId,
              name: node.name,
              code: node.code || '',
              categoryName,
              directionName,
            });
          }
          if (node.children) {
            const dirName = node.level === 'direction' ? node.name : directionName;
            const catName = node.level === 'category' ? node.name : categoryName;
            node.children.forEach(child => traverse(child, dirName, catName));
          }
        };
        if (data.children) {
          data.children.forEach(dir => traverse(dir, dir.name, ''));
        }
        setFlatCapabilities(flat);
      } catch (err) {
        console.error('Failed to fetch capability tree:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchTree();
  }, []);

  // Fetch capability detail
  const fetchCapabilityDetail = useCallback(async (id: number) => {
    setDetailLoading(true);
    try {
      const detail = await api.getCapability(id);
      setSelectedCapability(detail);
    } catch (err) {
      console.error('Failed to fetch capability detail:', err);
    } finally {
      setDetailLoading(false);
    }
  }, []);

  // Initialize G6 graph
  useEffect(() => {
    if (!containerRef.current || !treeData) return;

    // Destroy existing graph
    if (graphRef.current) {
      graphRef.current.destroy();
      graphRef.current = null;
    }

    const container = containerRef.current;
    const width = container.clientWidth;
    const height = container.clientHeight;

    const graph = new Graph({
      container,
      width,
      height,
      autoFit: 'view',
      padding: [40, 40, 40, 40],
      data: treeData,
      type: 'tree',
      layout: {
        type: 'mindmap',
        direction: 'H',
        getHeight: () => 28,
        getWidth: (node: TreeNode) => {
          if (node.level === 'root') return 120;
          if (node.level === 'direction') return 100;
          if (node.level === 'category') return 80;
          return 60;
        },
        getVGap: () => 8,
        getHGap: () => 60,
      },
      node: {
        type: 'rect',
        style: (model: TreeNode) => {
          const baseStyle = {
            radius: 4,
            cursor: 'pointer',
            labelText: model.name,
            labelFontSize: 11,
            labelFill: '#152033',
            labelPlacement: 'center',
          };

          if (model.level === 'root') {
            return {
              ...baseStyle,
              fill: '#2F6BFF',
              stroke: '#2F6BFF',
              labelFill: '#FFFFFF',
              labelFontSize: 13,
              fontWeight: 600,
              width: 120,
              height: 32,
            };
          }
          if (model.level === 'direction') {
            return {
              ...baseStyle,
              fill: '#E8F0FE',
              stroke: '#2F6BFF',
              lineWidth: 1.5,
              width: 100,
              height: 28,
            };
          }
          if (model.level === 'category') {
            return {
              ...baseStyle,
              fill: '#F0F7ED',
              stroke: '#16A37B',
              lineWidth: 1,
              width: 80,
              height: 26,
            };
          }
          // capability (leaf)
          return {
            ...baseStyle,
            fill: '#FFFFFF',
            stroke: '#E6EAF2',
            lineWidth: 1,
            width: 60,
            height: 24,
            labelFontSize: 10,
          };
        },
      },
      edge: {
        type: 'cubic-horizontal',
        style: {
          stroke: '#C7D1E0',
          lineWidth: 1,
        },
      },
      behaviors: [
        'drag-canvas',
        'zoom-canvas',
        'collapse-expand',
      ],
    });

    // Click handler for capability nodes
    graph.on('node:click', (evt: { target: { id: string } }) => {
      const nodeId = evt.target.id;
      // Find the node in tree data
      const findNode = (node: TreeNode): TreeNode | null => {
        if (node.id === nodeId) return node;
        if (node.children) {
          for (const child of node.children) {
            const found = findNode(child);
            if (found) return found;
          }
        }
        return null;
      };
      const found = findNode(treeData);
      if (found && found.level === 'capability' && found.capabilityId) {
        fetchCapabilityDetail(found.capabilityId);
      }
    });

    graph.render();
    graphRef.current = graph;

    // Resize handler
    const handleResize = () => {
      if (graphRef.current && container) {
        graphRef.current.resize(container.clientWidth, container.clientHeight);
      }
    };
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      if (graphRef.current) {
        graphRef.current.destroy();
        graphRef.current = null;
      }
    };
  }, [treeData, fetchCapabilityDetail]);

  // Filter capabilities by search
  const filteredCapabilities = flatCapabilities.filter(cap =>
    cap.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    cap.code.toLowerCase().includes(searchQuery.toLowerCase())
  );

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-muted-foreground">加载能力图谱...</div>
      </div>
    );
  }

  return (
    <div className="flex h-full">
      {/* Left Sidebar - Capability List */}
      <div className="w-72 border-r border-border bg-card flex flex-col">
        <div className="p-4 border-b border-border">
          <h3 className="text-sm font-semibold text-foreground mb-3">能力列表</h3>
          <input
            type="text"
            placeholder="搜索能力..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full px-3 py-2 text-sm bg-muted border border-border rounded-md focus:outline-none focus:ring-2 focus:ring-primary/30"
          />
        </div>
        <div className="flex-1 overflow-y-auto p-2">
          {filteredCapabilities.length === 0 ? (
            <div className="text-sm text-muted-foreground text-center py-8">
              {searchQuery ? '无匹配结果' : '暂无能力数据'}
            </div>
          ) : (
            <div className="space-y-1">
              {filteredCapabilities.slice(0, 100).map(cap => (
                <button
                  key={cap.id}
                  onClick={() => fetchCapabilityDetail(cap.id)}
                  className={`w-full text-left px-3 py-2 rounded-md text-sm transition-colors ${
                    selectedCapability?.id === cap.id
                      ? 'bg-primary/10 text-primary'
                      : 'hover:bg-muted text-foreground'
                  }`}
                >
                  <div className="font-medium truncate">{cap.name}</div>
                  <div className="text-xs text-muted-foreground truncate">
                    {cap.directionName} / {cap.categoryName}
                  </div>
                </button>
              ))}
              {filteredCapabilities.length > 100 && (
                <div className="text-xs text-muted-foreground text-center py-2">
                  显示前 100 条，共 {filteredCapabilities.length} 条
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Center - Graph */}
      <div className="flex-1 relative">
        <div ref={containerRef} className="w-full h-full" />
        <div className="absolute top-4 left-4 bg-card/90 backdrop-blur-sm rounded-lg px-3 py-2 text-xs text-muted-foreground shadow-sm">
          拖拽移动 | 滚轮缩放 | 点击节点展开/折叠 | 点击能力节点查看详情
        </div>
      </div>

      {/* Right Panel - Capability Detail */}
      {selectedCapability && (
        <div className="w-80 border-l border-border bg-card overflow-y-auto">
          <div className="p-4 border-b border-border flex items-center justify-between">
            <h3 className="text-sm font-semibold text-foreground">能力详情</h3>
            <button
              onClick={() => setSelectedCapability(null)}
              className="text-muted-foreground hover:text-foreground"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
          <div className="p-4 space-y-4">
            {detailLoading ? (
              <div className="text-sm text-muted-foreground">加载中...</div>
            ) : (
              <>
                {/* Basic Info */}
                <div>
                  <h4 className="text-lg font-semibold text-foreground mb-1">
                    {selectedCapability.name}
                  </h4>
                  <div className="text-xs text-muted-foreground">
                    {selectedCapability.code}
                  </div>
                </div>

                {/* Description */}
                {selectedCapability.description && (
                  <div>
                    <h5 className="text-xs font-medium text-muted-foreground uppercase mb-1">
                      描述
                    </h5>
                    <p className="text-sm text-foreground">
                      {selectedCapability.description}
                    </p>
                  </div>
                )}

                {/* Path */}
                {selectedCapability.path && selectedCapability.path.length > 0 && (
                  <div>
                    <h5 className="text-xs font-medium text-muted-foreground uppercase mb-1">
                      路径
                    </h5>
                    <div className="flex flex-wrap gap-1">
                      {selectedCapability.path.map((p, i) => (
                        <span key={i} className="text-xs">
                          {i > 0 && <span className="text-muted-foreground mx-1">/</span>}
                          <span className="text-foreground">{p.name}</span>
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Aliases */}
                {selectedCapability.aliases && selectedCapability.aliases.length > 0 && (
                  <div>
                    <h5 className="text-xs font-medium text-muted-foreground uppercase mb-2">
                      别名 ({selectedCapability.aliases.length})
                    </h5>
                    <div className="flex flex-wrap gap-1">
                      {selectedCapability.aliases.map(alias => (
                        <span
                          key={alias.id}
                          className="inline-flex items-center px-2 py-1 rounded-md text-xs bg-muted text-foreground"
                        >
                          {alias.name}
                          {alias.type && (
                            <span className="ml-1 text-muted-foreground">
                              ({alias.type})
                            </span>
                          )}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Relations */}
                {selectedCapability.relations && selectedCapability.relations.length > 0 && (
                  <div>
                    <h5 className="text-xs font-medium text-muted-foreground uppercase mb-2">
                      关联能力 ({selectedCapability.relations.length})
                    </h5>
                    <div className="space-y-1">
                      {selectedCapability.relations.map(rel => (
                        <button
                          key={rel.id}
                          onClick={() => fetchCapabilityDetail(rel.targetId)}
                          className="w-full text-left px-2 py-1 rounded text-xs hover:bg-muted transition-colors"
                        >
                          <span className="text-foreground">{rel.targetName}</span>
                          <span className="text-muted-foreground ml-1">({rel.type})</span>
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
