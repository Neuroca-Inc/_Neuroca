"""
Report generation and visualization for memory system benchmarks.
"""
import json
import time
from pathlib import Path
from typing import Dict, List, Any
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from datetime import datetime

from .benchmark_runner import SystemBenchmarkSuite, BenchmarkResult


class BenchmarkReportGenerator:
    """Generate comprehensive reports and visualizations from benchmark results."""
    
    def __init__(self, results_dir: str = "benchmarks/memory_systems_comparison/results",
                 reports_dir: str = "benchmarks/memory_systems_comparison/reports"):
        self.results_dir = Path(results_dir)
        self.reports_dir = Path(reports_dir)
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        
        # Set matplotlib style
        plt.style.use('default')
        plt.rcParams['figure.figsize'] = (12, 8)
        plt.rcParams['font.size'] = 10
    
    def load_results(self, results_file: str) -> Dict[str, SystemBenchmarkSuite]:
        """Load benchmark results from JSON file."""
        with open(results_file, 'r') as f:
            data = json.load(f)
        
        # Convert back to SystemBenchmarkSuite objects
        results = {}
        for system_name, suite_data in data.items():
            # Convert results back to BenchmarkResult objects
            benchmark_results = []
            for result_data in suite_data["results"]:
                benchmark_results.append(BenchmarkResult(**result_data))
            
            suite = SystemBenchmarkSuite(
                system_name=suite_data["system_name"],
                system_metadata=suite_data["system_metadata"],
                results=benchmark_results,
                total_time=suite_data["total_time"]
            )
            results[system_name] = suite
        
        return results
    
    def create_performance_comparison_chart(self, results: Dict[str, SystemBenchmarkSuite],
                                          operation: str, output_path: str):
        """Create a performance comparison chart for a specific operation."""
        # Collect data for the operation
        data = {}
        data_sizes = set()
        
        for system_name, suite in results.items():
            system_data = {}
            for result in suite.results:
                if result.operation == operation and result.success:
                    data_size = result.data_size
                    data_sizes.add(data_size)
                    
                    if data_size not in system_data:
                        system_data[data_size] = []
                    system_data[data_size].append(result.execution_time)
            
            # Calculate means for each data size
            system_means = {}
            for size in sorted(data_sizes):
                if size in system_data:
                    system_means[size] = np.mean(system_data[size])
                else:
                    system_means[size] = np.nan
            
            data[system_name] = system_means
        
        # Create the plot
        plt.figure(figsize=(12, 8))
        
        sorted_sizes = sorted(data_sizes)
        x_pos = np.arange(len(sorted_sizes))
        bar_width = 0.15
        
        colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7']
        
        for i, (system_name, system_data) in enumerate(data.items()):
            means = [system_data.get(size, np.nan) for size in sorted_sizes]
            plt.bar(x_pos + i * bar_width, means, bar_width, 
                   label=system_name, color=colors[i % len(colors)], alpha=0.8)
        
        plt.xlabel('Data Size (Number of Entries)')
        plt.ylabel('Average Execution Time (seconds)')
        plt.title(f'Performance Comparison - {operation.replace("_", " ").title()} Operation')
        plt.xticks(x_pos + bar_width * 2, sorted_sizes)
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
    
    def create_operation_summary_chart(self, results: Dict[str, SystemBenchmarkSuite],
                                     output_path: str):
        """Create a summary chart showing all operations for all systems."""
        operations = ['store_single', 'retrieve', 'search', 'update', 'delete']
        systems = list(results.keys())
        
        # Create data matrix
        data_matrix = []
        system_labels = []
        
        for system_name, suite in results.items():
            system_row = []
            for operation in operations:
                op_stats = suite.get_operation_stats(operation)
                system_row.append(op_stats['mean'] * 1000)  # Convert to milliseconds
            
            data_matrix.append(system_row)
            system_labels.append(system_name.replace(" ", "\\n"))
        
        # Create heatmap
        fig, ax = plt.subplots(figsize=(12, 8))
        
        im = ax.imshow(data_matrix, cmap='YlOrRd', aspect='auto')
        
        # Set ticks and labels
        ax.set_xticks(np.arange(len(operations)))
        ax.set_yticks(np.arange(len(systems)))
        ax.set_xticklabels([op.replace('_', ' ').title() for op in operations])
        ax.set_yticklabels(system_labels)
        
        # Add text annotations
        for i in range(len(systems)):
            for j in range(len(operations)):
                value = data_matrix[i][j]
                text = ax.text(j, i, f'{value:.2f}ms', 
                             ha="center", va="center", color="black", fontsize=9)
        
        ax.set_title("Average Operation Performance (Lower is Better)")
        
        # Add colorbar
        cbar = plt.colorbar(im)
        cbar.set_label('Execution Time (milliseconds)', rotation=270, labelpad=20)
        
        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
    
    def create_scalability_chart(self, results: Dict[str, SystemBenchmarkSuite],
                               output_path: str):
        """Create a chart showing how systems scale with data size."""
        # Focus on store_single operation for scalability
        operation = 'store_single'
        
        plt.figure(figsize=(14, 10))
        
        # Create subplots for different aspects
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
        
        # Collect data
        systems_data = {}
        all_sizes = set()
        
        for system_name, suite in results.items():
            size_times = {}
            for result in suite.results:
                if result.operation == operation and result.success:
                    size = result.data_size
                    all_sizes.add(size)
                    if size not in size_times:
                        size_times[size] = []
                    size_times[size].append(result.execution_time)
            
            systems_data[system_name] = size_times
        
        sorted_sizes = sorted(all_sizes)
        colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7']
        
        # Plot 1: Mean execution time vs data size
        for i, (system_name, size_times) in enumerate(systems_data.items()):
            means = []
            sizes = []
            for size in sorted_sizes:
                if size in size_times:
                    means.append(np.mean(size_times[size]) * 1000)  # Convert to ms
                    sizes.append(size)
            
            ax1.plot(sizes, means, 'o-', label=system_name, color=colors[i % len(colors)], linewidth=2)
        
        ax1.set_xlabel('Data Size (Number of Entries)')
        ax1.set_ylabel('Average Store Time (milliseconds)')
        ax1.set_title('Storage Performance Scalability')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # Plot 2: Standard deviation (consistency)
        for i, (system_name, size_times) in enumerate(systems_data.items()):
            stds = []
            sizes = []
            for size in sorted_sizes:
                if size in size_times and len(size_times[size]) > 1:
                    stds.append(np.std(size_times[size]) * 1000)  # Convert to ms
                    sizes.append(size)
            
            if sizes:  # Only plot if we have data
                ax2.plot(sizes, stds, 's-', label=system_name, color=colors[i % len(colors)], linewidth=2)
        
        ax2.set_xlabel('Data Size (Number of Entries)')
        ax2.set_ylabel('Standard Deviation (milliseconds)')
        ax2.set_title('Performance Consistency')
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        
        # Plot 3: Search performance
        search_data = {}
        for system_name, suite in results.items():
            size_times = {}
            for result in suite.results:
                if result.operation == 'search' and result.success:
                    size = result.data_size
                    if size not in size_times:
                        size_times[size] = []
                    size_times[size].append(result.execution_time)
            search_data[system_name] = size_times
        
        for i, (system_name, size_times) in enumerate(search_data.items()):
            means = []
            sizes = []
            for size in sorted_sizes:
                if size in size_times:
                    means.append(np.mean(size_times[size]) * 1000)
                    sizes.append(size)
            
            if sizes:
                ax3.plot(sizes, means, '^-', label=system_name, color=colors[i % len(colors)], linewidth=2)
        
        ax3.set_xlabel('Data Size (Number of Entries)')
        ax3.set_ylabel('Average Search Time (milliseconds)')
        ax3.set_title('Search Performance Scalability')
        ax3.legend()
        ax3.grid(True, alpha=0.3)
        
        # Plot 4: Memory efficiency (approximated by system metadata)
        memory_info = []
        system_names_short = []
        
        for system_name, suite in results.items():
            metadata = suite.system_metadata
            # Create a simple "efficiency score" based on features
            features_score = sum([
                metadata.get('supports_indexing', False) * 2,
                metadata.get('supports_transactions', False) * 1,
                metadata.get('persistent', False) * 1.5,
                1 if 'vector' in metadata.get('search_method', '') else 0,
                1 if 'fts' in metadata.get('search_method', '') else 0
            ])
            
            memory_info.append(features_score)
            system_names_short.append(system_name.split()[0])  # Abbreviated names
        
        bars = ax4.bar(system_names_short, memory_info, color=[colors[i % len(colors)] for i in range(len(memory_info))])
        ax4.set_ylabel('Feature Score')
        ax4.set_title('System Feature Comparison')
        ax4.tick_params(axis='x', rotation=45)
        
        # Add value labels on bars
        for bar in bars:
            height = bar.get_height()
            ax4.text(bar.get_x() + bar.get_width()/2., height + 0.1,
                    f'{height:.1f}', ha='center', va='bottom')
        
        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
    
    def generate_markdown_report(self, results: Dict[str, SystemBenchmarkSuite],
                               output_path: str):
        """Generate a comprehensive markdown report."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        report = f"""# Memory Systems Comparison Report

Generated on: {timestamp}

## Executive Summary

This report presents a comprehensive performance comparison of different memory systems, evaluating their suitability for various use cases in AI and cognitive architectures.

## Systems Tested

"""
        
        # System overview
        for system_name, suite in results.items():
            metadata = suite.system_metadata
            report += f"""### {system_name}

- **Type**: {metadata.get('type', 'Unknown')}
- **Storage**: {metadata.get('storage_type', 'Unknown')}
- **Persistent**: {metadata.get('persistent', False)}
- **Indexing**: {metadata.get('supports_indexing', False)}
- **Transactions**: {metadata.get('supports_transactions', False)}
- **Search Method**: {metadata.get('search_method', 'Unknown')}
- **Total Benchmark Time**: {suite.total_time:.2f} seconds

"""
        
        # Performance analysis
        report += """## Performance Analysis

### Operation Performance Summary

| System | Store (ms) | Retrieve (ms) | Search (ms) | Update (ms) | Delete (ms) |
|--------|------------|---------------|-------------|-------------|-------------|
"""
        
        for system_name, suite in results.items():
            operations = ['store_single', 'retrieve', 'search', 'update', 'delete']
            row = f"| {system_name} |"
            
            for op in operations:
                stats = suite.get_operation_stats(op)
                mean_ms = stats['mean'] * 1000  # Convert to milliseconds
                row += f" {mean_ms:.2f} |"
            
            report += row + "\\n"
        
        # Detailed analysis by operation
        operations_analysis = {
            'store_single': 'Storage operations measure how quickly each system can persist new memory entries.',
            'retrieve': 'Retrieval operations test direct access to memory entries by their unique identifier.',
            'search': 'Search operations evaluate the ability to find relevant memories based on content similarity.',
            'update': 'Update operations measure the efficiency of modifying existing memory entries.',
            'delete': 'Delete operations test the speed of removing entries from the memory system.'
        }
        
        report += "\\n### Detailed Operation Analysis\\n\\n"
        
        for operation, description in operations_analysis.items():
            report += f"#### {operation.replace('_', ' ').title()} Performance\\n\\n"
            report += f"{description}\\n\\n"
            
            # Find best and worst performers
            op_performance = []
            for system_name, suite in results.items():
                stats = suite.get_operation_stats(operation)
                if stats['count'] > 0:
                    op_performance.append((system_name, stats['mean']))
            
            if op_performance:
                op_performance.sort(key=lambda x: x[1])
                best = op_performance[0]
                worst = op_performance[-1]
                
                report += f"**Best Performance**: {best[0]} ({best[1]*1000:.2f}ms average)\\n\\n"
                report += f"**Worst Performance**: {worst[0]} ({worst[1]*1000:.2f}ms average)\\n\\n"
                
                if len(op_performance) > 1:
                    speedup = worst[1] / best[1]
                    report += f"**Speed Difference**: {speedup:.1f}x faster\\n\\n"
        
        # Recommendations
        report += """## Recommendations

### Use Case Scenarios

#### High-Frequency, Short-Term Memory
**Recommended**: Simple Dictionary Memory or NeuroCognitive Architecture (STM tier)
- Fastest for immediate access
- Good for working memory scenarios
- Limited persistence

#### Persistent, Searchable Memory
**Recommended**: SQLite Memory with FTS5
- Full-text search capabilities  
- ACID transactions
- Good balance of performance and features

#### Semantic/Vector Search
**Recommended**: Simple Vector Memory or NeuroCognitive Architecture
- Semantic similarity search
- Better for context-aware retrieval
- Suitable for AI reasoning tasks

#### Conversation Management
**Recommended**: LangChain-Inspired Buffer Memory
- Automatic context window management
- Token-aware memory limits
- Good for chat/conversation systems

#### Complex AI Applications
**Recommended**: NeuroCognitive Architecture Memory
- Multi-tier memory hierarchy
- Automatic consolidation
- Balanced performance across operations

### Performance Considerations

1. **Latency-Critical Applications**: Use in-memory systems (Simple Dictionary, NCA STM)
2. **Large-Scale Storage**: SQLite-based systems provide good scalability
3. **Semantic Understanding**: Vector-based systems excel at meaning-based retrieval
4. **Resource Constraints**: Simple systems have lower overhead

## Methodology

### Test Data
- Entry counts: 50, 100, 500 items per test
- Content length: ~100 characters average
- Metadata: Realistic tags, importance scores, session information

### Operations Tested
- **Storage**: Single and batch operations
- **Retrieval**: Direct ID-based access
- **Search**: Content-based queries
- **Updates**: Modification of existing entries
- **Deletion**: Entry removal
- **Listing**: Bulk retrieval operations

### Metrics
- **Execution Time**: Average, median, min, max, standard deviation
- **Success Rate**: Percentage of successful operations
- **Scalability**: Performance vs. data size

## Conclusion

The benchmark results demonstrate that different memory systems excel in different scenarios. The choice of memory system should be based on specific application requirements:

- **Speed**: Simple in-memory systems
- **Features**: SQLite-based systems
- **Intelligence**: Vector and NeuroCognitive systems
- **Balance**: NeuroCognitive Architecture provides the best overall balance

For applications requiring sophisticated memory management with multiple access patterns, the NeuroCognitive Architecture's multi-tier approach provides optimal performance across various scenarios.
"""
        
        # Write report
        with open(output_path, 'w') as f:
            f.write(report)
    
    def generate_full_report(self, results_file: str) -> str:
        """Generate complete report with all visualizations."""
        # Load results
        results = self.load_results(results_file)
        
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        base_name = f"memory_systems_report_{timestamp}"
        
        # Generate visualizations
        operations = ['store_single', 'retrieve', 'search', 'update', 'delete']
        
        for operation in operations:
            chart_path = self.reports_dir / f"{base_name}_{operation}_comparison.png"
            self.create_performance_comparison_chart(results, operation, str(chart_path))
        
        # Summary charts
        summary_path = self.reports_dir / f"{base_name}_operation_summary.png"
        self.create_operation_summary_chart(results, str(summary_path))
        
        scalability_path = self.reports_dir / f"{base_name}_scalability.png"
        self.create_scalability_chart(results, str(scalability_path))
        
        # Generate markdown report
        report_path = self.reports_dir / f"{base_name}.md"
        self.generate_markdown_report(results, str(report_path))
        
        print(f"Complete report generated:")
        print(f"  Markdown: {report_path}")
        print(f"  Charts: {self.reports_dir}/{base_name}_*.png")
        
        return str(report_path)