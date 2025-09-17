#!/usr/bin/env python3
"""
Demo script showing how to use the memory systems comparison benchmarks.
"""

import sys
from pathlib import Path

# Add the project root to the path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from benchmarks.memory_systems_comparison.benchmark_runner import MemorySystemBenchmark
from benchmarks.memory_systems_comparison.report_generator import BenchmarkReportGenerator


def run_quick_demo():
    """Run a quick demonstration of the benchmark system."""
    print("=" * 60)
    print("Memory Systems Comparison Benchmark Demo")
    print("=" * 60)
    
    print("\\n1. Running Quick Benchmark (small data sizes)...")
    
    # Create benchmark instance
    benchmark = MemorySystemBenchmark()
    
    # Run benchmarks with small data sizes for demo
    results = benchmark.run_comparison_benchmark(
        data_sizes=[25, 50],  # Small sizes for quick demo
        iterations=2
    )
    
    print("\\n2. Benchmark Results Summary:")
    print("-" * 40)
    
    for system_name, suite in results.items():
        successful_ops = len([r for r in suite.results if r.success])
        total_ops = len(suite.results)
        success_rate = (successful_ops / total_ops) * 100 if total_ops > 0 else 0
        
        print(f"{system_name}:")
        print(f"  Total Time: {suite.total_time:.3f}s")
        print(f"  Success Rate: {success_rate:.1f}% ({successful_ops}/{total_ops})")
        
        # Show performance for key operations
        for operation in ['store_single', 'retrieve', 'search']:
            stats = suite.get_operation_stats(operation)
            if stats['count'] > 0:
                print(f"  {operation.title()}: {stats['mean']*1000:.2f}ms avg")
        print()
    
    print("3. Finding Latest Results and Generating Report...")
    
    # Find the latest results file
    results_dir = Path("benchmarks/memory_systems_comparison/results")
    results_files = list(results_dir.glob("memory_systems_benchmark_*.json"))
    
    if results_files:
        latest_results = max(results_files, key=lambda p: p.stat().st_mtime)
        print(f"   Using: {latest_results.name}")
        
        # Generate report
        generator = BenchmarkReportGenerator()
        report_path = generator.generate_full_report(str(latest_results))
        
        print(f"   Report: {Path(report_path).name}")
        print(f"   Charts: {Path(report_path).parent}/*.png")
    
    print("\\n4. Key Findings:")
    print("-" * 40)
    
    # Sort systems by total time (performance)
    sorted_systems = sorted(results.items(), key=lambda x: x[1].total_time)
    
    print("Performance Ranking (by total time):")
    for i, (system_name, suite) in enumerate(sorted_systems, 1):
        print(f"  {i}. {system_name} ({suite.total_time:.3f}s)")
    
    print("\\nRecommendations:")
    print("  • For speed: Simple Dictionary Memory")
    print("  • For persistence: SQLite Memory")
    print("  • For conversations: LangChain-Inspired Buffer")
    print("  • For semantics: Vector Memory")
    print("  • For balance: NeuroCognitive Architecture")
    
    print("\\n" + "=" * 60)
    print("Demo completed! Check the reports/ directory for detailed analysis.")
    print("=" * 60)


if __name__ == "__main__":
    run_quick_demo()