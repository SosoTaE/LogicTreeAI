/**
 * Canvas Tree Visualization Engine
 * Renders conversation tree as an interactive node graph
 */

class TreeVisualizer {
    constructor(canvasId) {
        this.canvas = document.getElementById(canvasId);
        this.ctx = this.canvas.getContext('2d');

        // Visualization state
        this.tree = null;
        this.nodes = [];
        this.selectedNodeId = null;
        this.hoveredNodeId = null;
        this.draggedNode = null;
        this.manualPositions = {};

        // Pan and zoom state
        this.offsetX = 0;
        this.offsetY = 0;
        this.zoom = 1;
        this.isDragging = false;
        this.lastX = 0;
        this.lastY = 0;

        // Layout constants
        this.NODE_WIDTH = 220;
        this.NODE_HEIGHT = 80;
        this.HORIZONTAL_SPACING = 260;
        this.VERTICAL_SPACING = 140;

        // Theme Colors (matched to Tailwind theme)
        this.COLORS = {
            user: { bg: '#192540', border: '#85adff', text: '#dee5ff', glow: 'rgba(133,173,255,0.2)' },
            assistant: { bg: '#0f1930', border: '#ac8aff', text: '#dee5ff', glow: 'rgba(172,138,255,0.2)' },
            gpt: { border: '#10a37f', glow: 'rgba(16,163,127,0.2)' },
            claude: { border: '#ac8aff', glow: 'rgba(172,138,255,0.2)' },
            gemini: { border: '#fbbc04', glow: 'rgba(251,188,4,0.2)' },
            default: { bg: '#141f38', border: '#40485d', text: '#dee5ff', glow: 'rgba(64,72,93,0.2)' },
            selected: '#53ddfc',
            selectedGlow: 'rgba(83,221,252,0.4)',
            hover: '#dee5ff'
        };

        this.setupCanvas();
        this.setupEventListeners();
    }

    setupCanvas() {
        this.resizeCanvas();
        window.addEventListener('resize', () => this.resizeCanvas());
    }

    resizeCanvas() {
        const container = this.canvas.parentElement;
        this.canvas.width = container.clientWidth;
        this.canvas.height = container.clientHeight;
        this.draw();
    }

    setupEventListeners() {
        this.canvas.addEventListener('mousedown', (e) => this.handleMouseDown(e));
        this.canvas.addEventListener('mousemove', (e) => this.handleMouseMove(e));
        this.canvas.addEventListener('mouseup', (e) => this.handleMouseUp(e));
        this.canvas.addEventListener('mouseleave', () => { this.isDragging = false; this.draggedNode = null; });
        this.canvas.addEventListener('wheel', (e) => this.handleWheel(e));
        this.canvas.addEventListener('touchstart', (e) => this.handleTouchStart(e));
        this.canvas.addEventListener('touchmove', (e) => this.handleTouchMove(e));
        this.canvas.addEventListener('touchend', () => { this.isDragging = false; this.draggedNode = null; });
    }

    handleMouseDown(e) {
        const rect = this.canvas.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;

        const clickedNode = this.getNodeAtPosition(x, y);

        if (clickedNode) {
            this.selectedNodeId = clickedNode.id;
            this.draggedNode = clickedNode;
            this.lastX = x;
            this.lastY = y;
            this.draw();
            if (window.onNodeSelected) {
                window.onNodeSelected(clickedNode);
            }
        } else {
            this.isDragging = true;
            this.lastX = x;
            this.lastY = y;
        }
    }

    handleMouseMove(e) {
        const rect = this.canvas.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;

        if (this.draggedNode) {
            const dx = (x - this.lastX) / this.zoom;
            const dy = (y - this.lastY) / this.zoom;
            this.draggedNode.x += dx;
            this.draggedNode.y += dy;
            this.lastX = x;
            this.lastY = y;
            this.manualPositions[this.draggedNode.id] = { x: this.draggedNode.x, y: this.draggedNode.y };
            this.draw();
        } else if (this.isDragging) {
            const dx = x - this.lastX;
            const dy = y - this.lastY;
            this.offsetX += dx;
            this.offsetY += dy;
            this.lastX = x;
            this.lastY = y;
            this.draw();
        } else {
            const hoveredNode = this.getNodeAtPosition(x, y);
            const newHoveredId = hoveredNode ? hoveredNode.id : null;

            if (newHoveredId !== this.hoveredNodeId) {
                this.hoveredNodeId = newHoveredId;
                this.canvas.style.cursor = hoveredNode ? 'pointer' : (this.canvas.style.pointerEvents === 'auto' ? 'grab' : 'default');
                this.draw();
            }
        }
    }

    handleMouseUp(e) {
        this.isDragging = false;
        this.draggedNode = null;
        if(this.canvas.style.pointerEvents === 'auto') {
            this.canvas.style.cursor = 'grab';
        }
    }

    handleWheel(e) {
        e.preventDefault();
        const delta = e.deltaY > 0 ? 0.9 : 1.1;
        this.zoom *= delta;
        this.zoom = Math.max(0.2, Math.min(2.5, this.zoom));
        this.draw();
    }

    handleTouchStart(e) {
        if (e.touches.length === 1) {
            const touch = e.touches[0];
            const rect = this.canvas.getBoundingClientRect();
            const x = touch.clientX - rect.left;
            const y = touch.clientY - rect.top;
            
            const clickedNode = this.getNodeAtPosition(x, y);
            if (clickedNode) {
                this.selectedNodeId = clickedNode.id;
                this.draggedNode = clickedNode;
                this.lastX = x;
                this.lastY = y;
                this.draw();
                if (window.onNodeSelected) {
                    window.onNodeSelected(clickedNode);
                }
            } else {
                this.lastX = x;
                this.lastY = y;
                this.isDragging = true;
            }
        }
    }

    handleTouchMove(e) {
        e.preventDefault();
        if (e.touches.length === 1) {
            const touch = e.touches[0];
            const rect = this.canvas.getBoundingClientRect();
            const x = touch.clientX - rect.left;
            const y = touch.clientY - rect.top;

            if (this.draggedNode) {
                const dx = (x - this.lastX) / this.zoom;
                const dy = (y - this.lastY) / this.zoom;
                this.draggedNode.x += dx;
                this.draggedNode.y += dy;
                this.lastX = x;
                this.lastY = y;
                this.manualPositions[this.draggedNode.id] = { x: this.draggedNode.x, y: this.draggedNode.y };
                this.draw();
            } else if (this.isDragging) {
                const dx = x - this.lastX;
                const dy = y - this.lastY;
                this.offsetX += dx;
                this.offsetY += dy;
                this.lastX = x;
                this.lastY = y;
                this.draw();
            }
        }
    }

    getNodeAtPosition(x, y) {
        const treeX = (x - this.offsetX) / this.zoom;
        const treeY = (y - this.offsetY) / this.zoom;

        for (const node of this.nodes) {
            // Node bounds check
            const halfW = this.NODE_WIDTH / 2;
            const halfH = this.NODE_HEIGHT / 2;
            if (treeX >= node.x - halfW && treeX <= node.x + halfW &&
                treeY >= node.y - halfH && treeY <= node.y + halfH) {
                return node;
            }
        }

        return null;
    }

    loadTree(treeData, activeNodeId = null) {
        this.tree = treeData;
        this.selectedNodeId = activeNodeId;
        this.nodes = [];

        if (!treeData || treeData.length === 0) {
            this.draw();
            return;
        }

        this.calculateTreeLayout(treeData);
        this.centerView();
        this.draw();
    }

    calculateTreeLayout(tree) {
        const levelCounts = new Map();
        const queue = [];

        // Adjust tree so root starts at top
        tree.forEach((root, index) => {
            queue.push({ node: root, level: 0, parentX: null, index: index });
        });

        while (queue.length > 0) {
            const { node, level, parentX, index } = queue.shift();

            if (!levelCounts.has(level)) {
                levelCounts.set(level, 0);
            }

            const countAtLevel = levelCounts.get(level);

            let y = level * this.VERTICAL_SPACING + 100;
            let x;

            if (parentX !== null && node.children && node.children.length > 0) {
                const totalWidth = (node.children.length - 1) * this.HORIZONTAL_SPACING;
                x = parentX - totalWidth / 2 + countAtLevel * this.HORIZONTAL_SPACING;
            } else {
                x = countAtLevel * this.HORIZONTAL_SPACING - (levelCounts.get(level) * this.HORIZONTAL_SPACING / 2) + this.canvas.width/2;
            }

            if (this.manualPositions && this.manualPositions[node.id]) {
                x = this.manualPositions[node.id].x;
                y = this.manualPositions[node.id].y;
            }

            this.nodes.push({
                ...node,
                x: x,
                y: y,
                level: level
            });

            levelCounts.set(level, countAtLevel + 1);

            if (node.children && node.children.length > 0) {
                node.children.forEach((child, childIndex) => {
                    queue.push({
                        node: child,
                        level: level + 1,
                        parentX: x,
                        index: childIndex
                    });
                });
            }
        }
    }

    centerView() {
        if (this.nodes.length === 0) return;
        
        let minX = Infinity, maxX = -Infinity;
        let minY = Infinity, maxY = -Infinity;

        this.nodes.forEach(node => {
            minX = Math.min(minX, node.x);
            maxX = Math.max(maxX, node.x);
            minY = Math.min(minY, node.y);
            maxY = Math.max(maxY, node.y);
        });

        const treeWidth = maxX - minX;
        
        this.offsetX = (this.canvas.width - treeWidth * this.zoom) / 2 - minX * this.zoom;
        this.offsetY = 50;
    }

    draw() {
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

        if (this.nodes.length === 0) {
            this.drawEmptyState();
            return;
        }

        this.ctx.save();
        this.ctx.translate(this.offsetX, this.offsetY);
        this.ctx.scale(this.zoom, this.zoom);

        this.drawConnections();
        this.drawNodes();

        this.ctx.restore();
    }

    drawConnections() {
        this.nodes.forEach(node => {
            if (node.parent_id !== null) {
                const parent = this.nodes.find(n => n.id === node.parent_id);
                if (parent) {
                    this.ctx.beginPath();
                    const startX = parent.x;
                    const startY = parent.y + this.NODE_HEIGHT / 2;
                    const endX = node.x;
                    const endY = node.y - this.NODE_HEIGHT / 2;

                    this.ctx.moveTo(startX, startY);
                    this.ctx.bezierCurveTo(
                        startX, startY + 40,
                        endX, endY - 40,
                        endX, endY
                    );
                    
                    // Style connection
                    this.ctx.strokeStyle = 'rgba(109, 117, 140, 0.4)'; // outline-variant with opacity
                    this.ctx.lineWidth = 2;
                    
                    // Highlight path to selected node
                    if (this.selectedNodeId) {
                        const path = this.getPathToNode(this.selectedNodeId);
                        if (path && path.includes(node.id) && path.includes(parent.id)) {
                            this.ctx.strokeStyle = this.COLORS.selected;
                            this.ctx.lineWidth = 3;
                            
                            // Add glow to selected path
                            this.ctx.shadowColor = this.COLORS.selectedGlow;
                            this.ctx.shadowBlur = 10;
                        }
                    }

                    this.ctx.stroke();
                    this.ctx.shadowBlur = 0; // reset shadow
                }
            }
        });
    }

    getPathToNode(targetId) {
        const path = [];
        let current = this.nodes.find(n => n.id === targetId);
        
        while (current) {
            path.push(current.id);
            if (!current.parent_id) break;
            current = this.nodes.find(n => n.id === current.parent_id);
        }
        return path.reverse();
    }

    drawRoundRect(x, y, w, h, radius) {
        this.ctx.beginPath();
        this.ctx.moveTo(x + radius, y);
        this.ctx.lineTo(x + w - radius, y);
        this.ctx.quadraticCurveTo(x + w, y, x + w, y + radius);
        this.ctx.lineTo(x + w, y + h - radius);
        this.ctx.quadraticCurveTo(x + w, y + h, x + w - radius, y + h);
        this.ctx.lineTo(x + radius, y + h);
        this.ctx.quadraticCurveTo(x, y + h, x, y + h - radius);
        this.ctx.lineTo(x, y + radius);
        this.ctx.quadraticCurveTo(x, y, x + radius, y);
        this.ctx.closePath();
    }

    drawNodes() {
        this.nodes.forEach(node => {
            const isSelected = node.id === this.selectedNodeId;
            const isHovered = node.id === this.hoveredNodeId;
            
            const nodeLeft = node.x - this.NODE_WIDTH / 2;
            const nodeTop = node.y - this.NODE_HEIGHT / 2;

            const theme = this.getNodeTheme(node);

            // Glow effect
            if (isSelected || isHovered) {
                this.ctx.shadowColor = isSelected ? this.COLORS.selectedGlow : theme.glow;
                this.ctx.shadowBlur = isSelected ? 20 : 15;
                this.ctx.shadowOffsetX = 0;
                this.ctx.shadowOffsetY = 4;
            }

            // Draw Base Rectangle
            this.drawRoundRect(nodeLeft, nodeTop, this.NODE_WIDTH, this.NODE_HEIGHT, 12);
            this.ctx.fillStyle = theme.bg;
            this.ctx.fill();
            
            // Draw Border
            this.ctx.lineWidth = isSelected ? 2 : 1;
            this.ctx.strokeStyle = isSelected ? this.COLORS.selected : (isHovered ? this.COLORS.hover : theme.border);
            this.ctx.stroke();

            // Reset Shadow for interior elements
            this.ctx.shadowBlur = 0;

            // Draw Left Accent Bar
            this.drawRoundRect(nodeLeft, nodeTop, 6, this.NODE_HEIGHT, 12);
            // clip to only show the left rounded part
            this.ctx.save();
            this.ctx.clip();
            this.ctx.fillStyle = theme.border;
            this.ctx.fillRect(nodeLeft, nodeTop, 6, this.NODE_HEIGHT);
            this.ctx.restore();

            // Text Styles
            this.ctx.fillStyle = theme.text;
            this.ctx.textAlign = 'left';
            this.ctx.textBaseline = 'top';

            // Draw Role / Title
            this.ctx.font = 'bold 12px "Space Grotesk", sans-serif';
            const roleText = node.role.charAt(0).toUpperCase() + node.role.slice(1);
            this.ctx.fillText(roleText, nodeLeft + 20, nodeTop + 12);

            // Draw Model Used (if assistant)
            if (node.model_used) {
                this.ctx.font = '10px "JetBrains Mono", monospace';
                this.ctx.fillStyle = 'rgba(222, 229, 255, 0.6)'; // text-on-surface-variant
                this.ctx.textAlign = 'right';
                
                // Truncate model name if too long
                let modelStr = node.model_used;
                if(modelStr.length > 15) modelStr = modelStr.substring(0, 12) + '...';
                this.ctx.fillText(modelStr, nodeLeft + this.NODE_WIDTH - 12, nodeTop + 12);
            }

            // Draw Content Preview
            this.ctx.fillStyle = 'rgba(222, 229, 255, 0.8)';
            this.ctx.textAlign = 'left';
            this.ctx.font = '12px "Manrope", sans-serif';
            
            let preview = node.content.replace(/\n/g, ' ');
            if (preview.length > 50) preview = preview.substring(0, 47) + '...';
            
            // Split into two lines if needed
            const maxWidth = this.NODE_WIDTH - 32;
            this.wrapText(this.ctx, preview, nodeLeft + 20, nodeTop + 35, maxWidth, 16, 2);
        });
    }

    // Helper for text wrapping in canvas
    wrapText(context, text, x, y, maxWidth, lineHeight, maxLines) {
        const words = text.split(' ');
        let line = '';
        let currentLine = 0;

        for(let n = 0; n < words.length; n++) {
            const testLine = line + words[n] + ' ';
            const metrics = context.measureText(testLine);
            const testWidth = metrics.width;
            
            if (testWidth > maxWidth && n > 0) {
                context.fillText(line, x, y);
                line = words[n] + ' ';
                y += lineHeight;
                currentLine++;
                if(currentLine >= maxLines) break;
            }
            else {
                line = testLine;
            }
        }
        if(currentLine < maxLines) {
            context.fillText(line, x, y);
        }
    }

    getNodeTheme(node) {
        if (node.role === 'user') return this.COLORS.user;
        
        const model = (node.model_used || '').toLowerCase();
        let assistantTheme = { ...this.COLORS.assistant };
        
        if (model.includes('gpt') || model.includes('openai')) {
            assistantTheme.border = this.COLORS.gpt.border;
            assistantTheme.glow = this.COLORS.gpt.glow;
        } else if (model.includes('claude')) {
            assistantTheme.border = this.COLORS.claude.border;
            assistantTheme.glow = this.COLORS.claude.glow;
        } else if (model.includes('gemini')) {
            assistantTheme.border = this.COLORS.gemini.border;
            assistantTheme.glow = this.COLORS.gemini.glow;
        }

        return assistantTheme;
    }

    drawEmptyState() {
        this.ctx.fillStyle = '#6d758c'; // outline
        this.ctx.font = '14px "Space Grotesk", sans-serif';
        this.ctx.textAlign = 'center';
        this.ctx.textBaseline = 'middle';
        this.ctx.fillText('Canvas empty. Start a conversation.', this.canvas.width / 2, this.canvas.height / 2);
    }
    
    // Placeholder methods for zoom if controls are re-added
    zoomIn() {
        this.zoom *= 1.2;
        this.zoom = Math.min(2.5, this.zoom);
        this.draw();
    }

    zoomOut() {
        this.zoom *= 0.8;
        this.zoom = Math.max(0.2, this.zoom);
        this.draw();
    }

    resetView() {
        this.zoom = 1;
        this.centerView();
        this.draw();
    }
}

window.TreeVisualizer = TreeVisualizer;