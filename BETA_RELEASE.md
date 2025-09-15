# Neuroca Beta Release Guide

## Welcome to Neuroca 0.1.0-beta!

Neuroca (NeuroCognitive Architecture) is a biologically-inspired cognitive framework that enhances Large Language Models with persistent, dynamic, and human-like memory capabilities. This beta release represents a fully functional baseline implementation ready for evaluation and testing.

## 🎯 What's Included in this Beta

### ✅ Core Features Ready for Use

- **Three-Tiered Memory System**: Working, Episodic, and Semantic memory with automatic consolidation
- **Dynamic Memory Management**: Background processes for memory decay, consolidation, and relevance scoring
- **Health System**: Cognitive load monitoring and adaptive responses
- **API Interface**: RESTful API with FastAPI and comprehensive documentation
- **CLI Tools**: Command-line interface for system management and interaction
- **LLM Integration**: Support for OpenAI, Anthropic, and Ollama providers
- **Configuration System**: Flexible YAML/JSON configuration with environment variable support

### ⚠️ Beta Limitations

- Some cognitive control features are still in development
- Performance optimizations for large-scale deployments are ongoing
- Additional LLM provider integrations are planned
- Enhanced monitoring dashboards are in progress

## 🚀 Quick Start

### Prerequisites

- Python 3.9 or higher
- pip (recommended) or poetry
- Optional: Docker for containerized deployment

### Installation

```bash
# Install from PyPI (when available)
pip install neuroca

# Or install from source
git clone https://github.com/justinlietz93/_Neuroca.git
cd _Neuroca
pip install -e .
```

### Verify Installation

```bash
# Run the verification script
python verify_installation.py

# Or use the CLI
neuroca version
neuroca --help
```

### Basic Usage

```python
from neuroca.memory.models.memory_item import MemoryItem, MemoryContent
from neuroca.memory.backends.sqlite_backend import SQLiteBackend

# Create a memory item
content = MemoryContent(text="Important information to remember")
memory = MemoryItem(content=content, summary="Important info")

# Initialize memory backend
backend = SQLiteBackend()
# Store and retrieve memories
# (Full example in docs/user/getting-started.md)
```

### Start the API Server

```bash
# Start the API server
neuroca-api
# or
python -m uvicorn neuroca.api.main:app --host 127.0.0.1 --port 8000

# Access the documentation at http://127.0.0.1:8000/docs
```

## 📊 Test Results

The beta release has been validated with:

- **200+ unit tests** covering core functionality
- **Integration tests** for memory system operations
- **API endpoint testing** with automated verification
- **CLI command validation** for all primary functions

Recent verification shows **10/11 core tests passing**, indicating solid baseline functionality.

## 📚 Documentation

### Essential Reading

1. **[Getting Started Guide](docs/user/getting-started.md)** - Setup and first steps
2. **[Configuration Guide](docs/user/configuration.md)** - System configuration options
3. **[API Documentation](docs/api/endpoints.md)** - Complete API reference
4. **[Architecture Overview](docs/architecture/components.md)** - System design and components

### Advanced Topics

- **[Memory System Deep Dive](docs/architecture/memory_system_backend_configuration.md)**
- **[Health System Documentation](docs/architecture/diagrams/health-system/overview.md)**
- **[LangChain Integration](docs/langchain/index.md)**
- **[Development Environment Setup](docs/development/environment.md)**

## 🔧 Configuration

### Basic Configuration

Create a `neuroca.yaml` file:

```yaml
memory:
  working:
    capacity: 7
    decay_rate: 0.05
  long_term:
    storage_path: "./data/memory"
    similarity_threshold: 0.75

llm:
  provider: "openai"  # or "anthropic", "ollama"
  model: "gpt-4"
  temperature: 0.7

health:
  enabled: true
  initial_values:
    energy: 100
    stability: 100
```

### Environment Variables

```bash
export NEUROCA_LLM_PROVIDER=openai
export OPENAI_API_KEY=your_api_key_here
export NEUROCA_MEMORY_WORKING_CAPACITY=5
```

## 🧪 Testing & Validation

### Run the Test Suite

```bash
# Install test dependencies
pip install pytest pytest-asyncio

# Run tests
python -c "import pytest; pytest.main(['tests/unit/', '-v'])"
```

### Validate Core Functionality

```bash
# Comprehensive verification
python verify_installation.py

# Test specific components
neuroca memory --help
neuroca health --help
```

## 🐛 Known Issues & Workarounds

### Common Setup Issues

1. **Missing CLI log directory**: Creates automatically on first run
2. **Database configuration warnings**: Expected in development mode
3. **LLM integration warnings**: Requires API key configuration

### Performance Considerations

- Memory capacity settings affect performance (default: 7 items in working memory)
- Embedding model choice impacts similarity search speed
- Consider SQLite vs PostgreSQL for production deployments

## 🎯 Use Cases for Beta Testing

### Ideal for Testing

- **Educational tools** with personalized learning memory
- **Chatbots** requiring conversational context persistence
- **Research applications** studying memory and cognition
- **Content assistants** maintaining user preferences and context

### Production Readiness

- Core memory operations: ✅ Ready
- Basic API endpoints: ✅ Ready
- CLI management tools: ✅ Ready
- Docker deployment: ✅ Ready
- High-throughput scenarios: ⚠️ Needs optimization

## 🤝 Contributing & Feedback

### Report Issues

- **Bugs**: [GitHub Issues](https://github.com/justinlietz93/_Neuroca/issues)
- **Feature Requests**: [GitHub Discussions](https://github.com/justinlietz93/_Neuroca/discussions)
- **Documentation**: [Create an issue](https://github.com/justinlietz93/_Neuroca/issues/new) with label `documentation`

### Contributing

1. Review [Contributing Guidelines](docs/development/contributing.md)
2. Check [Development Standards](docs/development/standards.md)
3. Follow [Development Workflow](docs/development/workflow.md)

### Beta Feedback

We're particularly interested in feedback on:

- Memory system performance with your use case
- API usability and completeness
- Documentation clarity and completeness
- Installation and setup experience
- Integration with existing LLM workflows

## 🗺️ Roadmap

### Immediate Priorities (Post-Beta)

- Performance optimization for large datasets
- Enhanced cognitive control features
- Additional LLM provider support
- Comprehensive monitoring dashboard

### Future Releases

- Advanced reasoning capabilities
- Multi-agent memory sharing
- Real-time collaboration features
- Enhanced embedding model support

## 📞 Support

### Getting Help

1. **Documentation**: [docs.neuroca.dev](https://docs.neuroca.dev)
2. **Examples**: [docs/user/examples.md](docs/user/examples.md)
3. **API Reference**: [docs/api/endpoints.md](docs/api/endpoints.md)
4. **GitHub Discussions**: Community support and questions

### Professional Support

For enterprise deployments or custom integrations, contact: jlietz93@gmail.com

---

## 🎉 Thank You!

Thank you for participating in the Neuroca beta program. Your feedback and testing help make this cognitive architecture better for everyone.

**Happy building with persistent AI memory!**

---

*Neuroca Beta Release - September 2025*  
*Version 0.1.0-beta*