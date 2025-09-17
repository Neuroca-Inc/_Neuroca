"""
Main entry point for memory systems comparison benchmarks.
"""
import argparse
import sys
from pathlib import Path

from .benchmark_runner import MemorySystemBenchmark, run_benchmark
from .report_generator import BenchmarkReportGenerator


def main():
    """Main function for running memory system benchmarks and generating reports."""
    parser = argparse.ArgumentParser(
        description="Memory Systems Comparison Benchmark Suite",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m benchmarks.memory_systems_comparison run
  python -m benchmarks.memory_systems_comparison run --data-sizes 100 500 1000 --iterations 5
  python -m benchmarks.memory_systems_comparison report results/memory_systems_benchmark_20240101_120000.json
  python -m benchmarks.memory_systems_comparison full --data-sizes 50 100 --iterations 3
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Run benchmark command
    run_parser = subparsers.add_parser('run', help='Run the benchmark suite')
    run_parser.add_argument(
        '--data-sizes', 
        nargs='+', 
        type=int, 
        default=[50, 100, 500],
        help='Data sizes to test (default: 50 100 500)'
    )
    run_parser.add_argument(
        '--iterations', 
        type=int, 
        default=3,
        help='Number of iterations per test (default: 3)'
    )
    run_parser.add_argument(
        '--output-dir',
        type=str,
        default='benchmarks/memory_systems_comparison/results',
        help='Output directory for results'
    )
    
    # Generate report command
    report_parser = subparsers.add_parser('report', help='Generate report from existing results')
    report_parser.add_argument(
        'results_file',
        type=str,
        help='Path to benchmark results JSON file'
    )
    report_parser.add_argument(
        '--output-dir',
        type=str,
        default='benchmarks/memory_systems_comparison/reports',
        help='Output directory for reports'
    )
    
    # Full workflow command
    full_parser = subparsers.add_parser('full', help='Run benchmarks and generate report')
    full_parser.add_argument(
        '--data-sizes', 
        nargs='+', 
        type=int, 
        default=[50, 100, 500],
        help='Data sizes to test (default: 50 100 500)'
    )
    full_parser.add_argument(
        '--iterations', 
        type=int, 
        default=3,
        help='Number of iterations per test (default: 3)'
    )
    
    args = parser.parse_args()
    
    if args.command == 'run':
        print("Running Memory Systems Comparison Benchmark...")
        benchmark = MemorySystemBenchmark(output_dir=args.output_dir)
        results = benchmark.run_comparison_benchmark(
            data_sizes=args.data_sizes,
            iterations=args.iterations
        )
        
        print("\\nBenchmark Results Summary:")
        for system_name, suite in results.items():
            print(f"  {system_name}: {suite.total_time:.2f}s total time")
        
    elif args.command == 'report':
        print(f"Generating report from {args.results_file}...")
        
        if not Path(args.results_file).exists():
            print(f"Error: Results file {args.results_file} not found")
            sys.exit(1)
        
        generator = BenchmarkReportGenerator(reports_dir=args.output_dir)
        report_path = generator.generate_full_report(args.results_file)
        print(f"Report generated: {report_path}")
        
    elif args.command == 'full':
        print("Running full benchmark and report generation workflow...")
        
        # Run benchmarks
        benchmark = MemorySystemBenchmark()
        results = benchmark.run_comparison_benchmark(
            data_sizes=args.data_sizes,
            iterations=args.iterations
        )
        
        # Find the latest results file
        results_dir = Path("benchmarks/memory_systems_comparison/results")
        results_files = list(results_dir.glob("memory_systems_benchmark_*.json"))
        
        if not results_files:
            print("Error: No results files found")
            sys.exit(1)
        
        latest_results = max(results_files, key=lambda p: p.stat().st_mtime)
        
        # Generate report
        generator = BenchmarkReportGenerator()
        report_path = generator.generate_full_report(str(latest_results))
        
        print(f"\\nComplete workflow finished!")
        print(f"Results: {latest_results}")
        print(f"Report: {report_path}")
        
    else:
        parser.print_help()


if __name__ == "__main__":
    main()