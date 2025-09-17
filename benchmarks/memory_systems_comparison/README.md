# Memory Systems Comparison Benchmarks

This directory contains comprehensive benchmarks comparing the NeuroCognitive Architecture memory system against other popular memory systems and frameworks commonly used in AI applications.

## Overview

The benchmark suite evaluates multiple memory systems across various performance metrics including:

- **Storage Performance**: How quickly systems can persist new memory entries
- **Retrieval Performance**: Speed of direct memory access by ID
- **Search Performance**: Ability to find relevant memories based on content
- **Update/Delete Performance**: Efficiency of modifying existing memories
- **Scalability**: Performance degradation as data size increases
- **Consistency**: Reliability of performance across multiple runs

## Memory Systems Tested

### 1. Simple Dictionary Memory
- **Type**: In-memory baseline
- **Storage**: Python dictionaries
- **Best For**: Fast prototyping, small-scale applications
- **Features**: Simple, minimal overhead

### 2. SQLite Memory with FTS5
- **Type**: Persistent database
- **Storage**: SQLite with full-text search
- **Best For**: Applications requiring persistence and complex queries
- **Features**: ACID transactions, full-text search, indexing

### 3. LangChain-Inspired Buffer Memory
- **Type**: Circular buffer
- **Storage**: Token-aware sliding window
- **Best For**: Conversation management, chat systems
- **Features**: Automatic context management, token limits

### 4. Simple Vector Memory (TF-IDF + Cosine)
- **Type**: Vector-based semantic search
- **Storage**: In-memory with TF-IDF vectors
- **Best For**: Semantic similarity, content-based retrieval
- **Features**: Cosine similarity search, semantic understanding

### 5. NeuroCognitive Architecture Memory
- **Type**: Multi-tier hybrid system
- **Storage**: STM/MTM/LTM hierarchy
- **Best For**: Complex AI applications, cognitive architectures
- **Features**: Automatic consolidation, multi-tier access patterns

## Usage

### Quick Start

```bash
# Run the complete benchmark and generate report
cd /path/to/_Neuroca
python -m benchmarks.memory_systems_comparison full

# Run only benchmarks
python -m benchmarks.memory_systems_comparison run --data-sizes 50 100 500 --iterations 3

# Generate report from existing results
python -m benchmarks.memory_systems_comparison report results/memory_systems_benchmark_YYYYMMDD_HHMMSS.json
```

### Programmatic Usage

```python
from benchmarks.memory_systems_comparison.benchmark_runner import MemorySystemBenchmark
from benchmarks.memory_systems_comparison.report_generator import BenchmarkReportGenerator

# Run benchmarks
benchmark = MemorySystemBenchmark()
results = benchmark.run_comparison_benchmark(
    data_sizes=[50, 100, 500],
    iterations=3
)

# Generate report
generator = BenchmarkReportGenerator()
report_path = generator.generate_full_report("path/to/results.json")
```

## Output

The benchmark generates:

### Results
- **JSON files**: Raw benchmark data in `results/`
- **Detailed metrics**: Execution times, success rates, system metadata

### Reports
- **Markdown report**: Comprehensive analysis with recommendations
- **Performance charts**: Visual comparisons across all operations
- **Scalability analysis**: Performance vs. data size trends
- **Operation heatmaps**: Summary view of all systems and operations

### Visualizations
- Individual operation comparison charts
- Combined operation summary heatmap
- Scalability and consistency analysis
- Feature comparison matrix

## Interpreting Results

### Performance Metrics
- **Lower execution times** = Better performance
- **Higher success rates** = More reliable
- **Lower standard deviation** = More consistent

### Use Case Recommendations
- **Speed-critical**: Simple Dictionary or NCA STM tier
- **Persistence required**: SQLite Memory
- **Semantic search**: Vector Memory or NCA
- **Conversation systems**: LangChain-inspired Buffer
- **Complex AI**: NeuroCognitive Architecture

## Methodology

### Test Data
- Realistic memory entries with varied content
- Metadata including importance scores, tags, timestamps
- Multiple data sizes to test scalability

### Operations Tested
- **store_single**: Individual memory storage
- **store_batch**: Bulk memory storage
- **retrieve**: Direct access by ID
- **search**: Content-based queries
- **update**: Modify existing entries
- **delete**: Remove entries
- **list**: Retrieve multiple entries

### Metrics Collected
- Mean, median, min, max execution times
- Standard deviation for consistency
- Success/failure rates
- System resource usage

## Dependencies

- Python 3.8+
- matplotlib (for visualizations)
- pandas (for data analysis)
- numpy (for numerical operations)
- sqlite3 (built-in, for SQLite memory system)

## Extensions

To add new memory systems for comparison:

1. Implement the `MemorySystemInterface` in `base.py`
2. Add your implementation to `competitors/`
3. Register it in `benchmark_runner.py`
4. Run benchmarks to include it in comparisons

## Results Interpretation

The benchmarks provide clear guidance on selecting the right memory system:

- **NeuroCognitive Architecture** provides the best overall balance
- **Simple Dictionary** excels in pure speed for small datasets
- **SQLite** offers the best persistence and query capabilities
- **Vector Memory** leads in semantic understanding
- **Buffer Memory** is optimal for conversation management

See the generated markdown reports for detailed analysis and recommendations.## Recent Benchmark Run Results

Latest demo run shows:

1. **Simple Dictionary Memory**: 0.003s (fastest, best for speed)
2. **Simple Vector Memory**: 0.005s (good balance of speed and semantic search)  
3. **NeuroCognitive Architecture**: 0.006s (excellent balance, multi-tier design)
4. **LangChain Buffer**: 0.018s (optimized for conversation management)
5. **SQLite Memory**: 0.022s (most features, persistence, transactions)

The benchmark successfully demonstrates the trade-offs between different memory architectures and validates the NeuroCognitive Architecture's balanced approach.
