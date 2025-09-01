#!/usr/bin/env python3
"""
OnMemOS v3 Agentic Service Demo
Demonstrates building an agentic service (like ChatGPT with agents) using OnMemOS SDK.

This example shows:
1. Current SDK capabilities for agent-based services
2. Multi-agent orchestration
3. Resource management and cost control
4. What might be missing for production agentic services
"""

import sys
import os
import time
import json
import asyncio
import logging
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from contextlib import asynccontextmanager

# Add the SDK to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'sdk', 'python'))

from client import OnMemOSClient
from server.models.sessions import CPUSize, MemorySize, GPUType, ImageType
from server.models.users import WorkspaceResourcePackage

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class AgentConfig:
    """Configuration for an agent"""
    name: str
    workspace_id: str
    namespace: str
    user_id: str
    cpu_size: CPUSize = CPUSize.MEDIUM
    memory_size: MemorySize = MemorySize.MEDIUM
    gpu_type: Optional[GPUType] = None
    image_type: ImageType = ImageType.PYTHON_PRO
    persistent_storage_gb: int = 20
    ttl_minutes: int = 120
    auto_cleanup: bool = True

@dataclass
class AgentTask:
    """A task for an agent to execute"""
    id: str
    agent_name: str
    command: str
    expected_output: Optional[str] = None
    timeout: int = 300
    dependencies: List[str] = None  # Task IDs this depends on

class AgenticService:
    """
    A service that manages multiple agents for complex tasks.
    
    This demonstrates how to build an agentic service using OnMemOS SDK.
    """
    
    def __init__(self, client: OnMemOSClient, base_workspace_id: str = "agentic-service"):
        self.client = client
        self.base_workspace_id = base_workspace_id
        self.agents: Dict[str, Dict[str, Any]] = {}  # agent_name -> session_info
        self.tasks: Dict[str, AgentTask] = {}
        self.results: Dict[str, Dict[str, Any]] = {}
        
        # Ensure workspace exists
        self._ensure_workspace()
    
    def _ensure_workspace(self):
        """Ensure the base workspace exists"""
        try:
            workspace = self.client.get_workspace("service-admin", self.base_workspace_id)
            logger.info(f"Using existing workspace: {self.base_workspace_id}")
        except Exception:
            logger.info(f"Creating workspace: {self.base_workspace_id}")
            self.client.create_workspace(
                user_id="service-admin",
                workspace_id=self.base_workspace_id,
                name="Agentic Service Workspace",
                resource_package=WorkspaceResourcePackage.ENTERPRISE_LARGE,
                description="Workspace for agentic service operations"
            )
    
    def create_agent(self, config: AgentConfig) -> str:
        """
        Create an agent with the specified configuration.
        
        Returns:
            Agent session ID
        """
        logger.info(f"Creating agent: {config.name}")
        
        # Create agent session
        session = self.client.create_session_in_workspace(
            workspace_id=config.workspace_id,
            template="python",
            namespace=config.namespace,
            user=config.user_id,
            resource_spec=self.client.resource_spec(
                cpu_size=config.cpu_size,
                memory_size=config.memory_size
            ),
            image_type=config.image_type,
            gpu_type=config.gpu_type,
            request_persistent_storage=True,
            persistent_storage_size_gb=config.persistent_storage_gb,
            ttl_minutes=config.ttl_minutes
        )
        
        session_id = session["id"]
        self.agents[config.name] = {
            "session": session,
            "config": config,
            "status": "created"
        }
        
        logger.info(f"Agent {config.name} created with session ID: {session_id}")
        return session_id
    
    def setup_agent_environment(self, agent_name: str, setup_commands: List[str]):
        """Set up the environment for an agent"""
        if agent_name not in self.agents:
            raise ValueError(f"Agent {agent_name} not found")
        
        agent_info = self.agents[agent_name]
        session_id = agent_info["session"]["id"]
        
        logger.info(f"Setting up environment for agent: {agent_name}")
        
        for command in setup_commands:
            result = self.client.execute_session(session_id, command)
            if not result.get("success"):
                logger.error(f"Setup command failed for {agent_name}: {command}")
                logger.error(f"Error: {result.get('error', 'Unknown error')}")
                raise Exception(f"Agent setup failed: {command}")
        
        agent_info["status"] = "ready"
        logger.info(f"Agent {agent_name} environment setup complete")
    
    def execute_task(self, task: AgentTask) -> Dict[str, Any]:
        """Execute a task on the specified agent"""
        if task.agent_name not in self.agents:
            raise ValueError(f"Agent {task.agent_name} not found")
        
        agent_info = self.agents[task.agent_name]
        session_id = agent_info["session"]["id"]
        
        logger.info(f"Executing task {task.id} on agent {task.agent_name}")
        
        # Check dependencies
        if task.dependencies:
            for dep_id in task.dependencies:
                if dep_id not in self.results:
                    raise Exception(f"Task dependency {dep_id} not completed")
        
        # Execute the task
        result = self.client.execute_session(
            session_id=session_id,
            command=task.command,
            timeout=task.timeout
        )
        
        # Store result
        self.results[task.id] = {
            "task": task,
            "result": result,
            "timestamp": time.time(),
            "agent": task.agent_name
        }
        
        logger.info(f"Task {task.id} completed: success={result.get('success', False)}")
        return result
    
    def cleanup_agent(self, agent_name: str):
        """Clean up an agent session"""
        if agent_name not in self.agents:
            return
        
        agent_info = self.agents[agent_name]
        session_id = agent_info["session"]["id"]
        
        logger.info(f"Cleaning up agent: {agent_name}")
        self.client.delete_session(session_id)
        
        del self.agents[agent_name]
        logger.info(f"Agent {agent_name} cleaned up")
    
    def cleanup_all_agents(self):
        """Clean up all agents"""
        agent_names = list(self.agents.keys())
        for agent_name in agent_names:
            self.cleanup_agent(agent_name)
    
    def get_cost_estimate(self) -> Dict[str, Any]:
        """Get cost estimate for all running agents"""
        total_cost = 0
        agent_costs = {}
        
        for agent_name, agent_info in self.agents.items():
            config = agent_info["config"]
            
            # Estimate cost based on configuration
            cpu_cost = {
                CPUSize.SMALL: 0.05,
                CPUSize.MEDIUM: 0.10,
                CPUSize.LARGE: 0.20,
                CPUSize.XLARGE: 0.40
            }.get(config.cpu_size, 0.10)
            
            memory_cost = {
                MemorySize.SMALL: 0.02,
                MemorySize.MEDIUM: 0.05,
                MemorySize.LARGE: 0.10,
                MemorySize.XLARGE: 0.20
            }.get(config.memory_size, 0.05)
            
            gpu_cost = 0.50 if config.gpu_type else 0.0
            storage_cost = 0.01 * config.persistent_storage_gb
            
            hourly_cost = cpu_cost + memory_cost + gpu_cost + storage_cost
            total_hours = config.ttl_minutes / 60
            total_agent_cost = hourly_cost * total_hours
            
            agent_costs[agent_name] = {
                "hourly_cost": hourly_cost,
                "total_cost": total_agent_cost,
                "configuration": {
                    "cpu": config.cpu_size.value,
                    "memory": config.memory_size.value,
                    "gpu": config.gpu_type.value if config.gpu_type else None,
                    "storage_gb": config.persistent_storage_gb
                }
            }
            
            total_cost += total_agent_cost
        
        return {
            "total_cost": total_cost,
            "agent_costs": agent_costs,
            "currency": "USD",
            "estimated_hours": sum(info["config"].ttl_minutes / 60 for info in self.agents.values())
        }

# ============================================================================
# Example: Multi-Agent Data Analysis Pipeline
# ============================================================================

def demo_data_analysis_pipeline():
    """Demonstrate a multi-agent data analysis pipeline"""
    print("🚀 OnMemOS v3 Agentic Service Demo: Data Analysis Pipeline")
    print("=" * 60)
    
    # Initialize client and service
    client = OnMemOSClient()
    service = AgenticService(client, "data-analysis-demo")
    
    try:
        # Create specialized agents
        agents = [
            AgentConfig(
                name="data-collector",
                workspace_id="data-analysis-demo",
                namespace="data-pipeline",
                user_id="service-admin",
                cpu_size=CPUSize.MEDIUM,
                memory_size=MemorySize.MEDIUM,
                image_type=ImageType.PYTHON_PRO,
                persistent_storage_gb=50,
                ttl_minutes=180
            ),
            AgentConfig(
                name="data-processor",
                workspace_id="data-analysis-demo",
                namespace="data-pipeline",
                user_id="service-admin",
                cpu_size=CPUSize.LARGE,
                memory_size=MemorySize.LARGE,
                image_type=ImageType.PYTHON_PRO,
                persistent_storage_gb=100,
                ttl_minutes=240
            ),
            AgentConfig(
                name="ml-trainer",
                workspace_id="data-analysis-demo",
                namespace="data-pipeline",
                user_id="service-admin",
                cpu_size=CPUSize.XLARGE,
                memory_size=MemorySize.XLARGE,
                gpu_type=GPUType.T4,
                image_type=ImageType.PYTHON_ENTERPRISE,
                persistent_storage_gb=200,
                ttl_minutes=300
            ),
            AgentConfig(
                name="results-analyzer",
                workspace_id="data-analysis-demo",
                namespace="data-pipeline",
                user_id="service-admin",
                cpu_size=CPUSize.MEDIUM,
                memory_size=MemorySize.MEDIUM,
                image_type=ImageType.PYTHON_PRO,
                persistent_storage_gb=30,
                ttl_minutes=120
            )
        ]
        
        # Create all agents
        print("\n📦 Creating agents...")
        for agent_config in agents:
            service.create_agent(agent_config)
        
        # Set up environments
        print("\n🔧 Setting up agent environments...")
        
        # Data collector setup
        service.setup_agent_environment("data-collector", [
            "pip install requests pandas numpy",
            "mkdir -p /persist/data"
        ])
        
        # Data processor setup
        service.setup_agent_environment("data-processor", [
            "pip install pandas numpy scipy scikit-learn",
            "mkdir -p /persist/processed"
        ])
        
        # ML trainer setup
        service.setup_agent_environment("ml-trainer", [
            "pip install torch torchvision transformers datasets",
            "mkdir -p /persist/models"
        ])
        
        # Results analyzer setup
        service.setup_agent_environment("results-analyzer", [
            "pip install pandas matplotlib seaborn plotly",
            "mkdir -p /persist/results"
        ])
        
        # Define tasks
        tasks = [
            AgentTask(
                id="collect-data",
                agent_name="data-collector",
                command="""
                python -c "
import requests
import pandas as pd
import json

# Simulate data collection
print('Collecting sample data...')
data = {
    'feature1': [1, 2, 3, 4, 5],
    'feature2': [10, 20, 30, 40, 50],
    'target': [0, 1, 0, 1, 1]
}
df = pd.DataFrame(data)
df.to_csv('/persist/data/sample_data.csv', index=False)
print('Data collected and saved to /persist/data/sample_data.csv')
print(json.dumps({'status': 'success', 'rows': len(df)}))
"
                """,
                timeout=60
            ),
            AgentTask(
                id="process-data",
                agent_name="data-processor",
                command="""
                python -c "
import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler

# Load and process data
print('Processing data...')
df = pd.read_csv('/persist/data/sample_data.csv')

# Add some features
df['feature3'] = df['feature1'] * df['feature2']
df['feature4'] = np.sqrt(df['feature1'])

# Scale features
scaler = StandardScaler()
features = ['feature1', 'feature2', 'feature3', 'feature4']
df[features] = scaler.fit_transform(df[features])

# Save processed data
df.to_csv('/persist/processed/processed_data.csv', index=False)
print('Data processed and saved to /persist/processed/processed_data.csv')
print(f'Processed {len(df)} rows with {len(features)} features')
"
                """,
                dependencies=["collect-data"],
                timeout=120
            ),
            AgentTask(
                id="train-model",
                agent_name="ml-trainer",
                command="""
                python -c "
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
import joblib

# Load processed data
print('Training ML model...')
df = pd.read_csv('/persist/processed/processed_data.csv')

# Prepare features and target
X = df[['feature1', 'feature2', 'feature3', 'feature4']]
y = df['target']

# Split data
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# Train model
model = RandomForestClassifier(n_estimators=100, random_state=42)
model.fit(X_train, y_train)

# Evaluate
train_score = model.score(X_train, y_train)
test_score = model.score(X_test, y_test)

# Save model
joblib.dump(model, '/persist/models/random_forest_model.pkl')

print(f'Model trained successfully!')
print(f'Train accuracy: {train_score:.3f}')
print(f'Test accuracy: {test_score:.3f}')
print('Model saved to /persist/models/random_forest_model.pkl')
"
                """,
                dependencies=["process-data"],
                timeout=180
            ),
            AgentTask(
                id="analyze-results",
                agent_name="results-analyzer",
                command="""
                python -c "
import pandas as pd
import numpy as np
import json
from sklearn.ensemble import RandomForestClassifier
import joblib

# Load data and model
print('Analyzing results...')
df = pd.read_csv('/persist/processed/processed_data.csv')
model = joblib.load('/persist/models/random_forest_model.pkl')

# Generate analysis
analysis = {
    'dataset_size': len(df),
    'features': list(df.columns[:-1]),  # Exclude target
    'target_distribution': df['target'].value_counts().to_dict(),
    'feature_importance': dict(zip(df.columns[:-1], model.feature_importances_)),
    'model_type': 'RandomForestClassifier',
    'n_estimators': 100
}

# Save analysis
with open('/persist/results/analysis.json', 'w') as f:
    json.dump(analysis, f, indent=2)

print('Analysis completed!')
print(json.dumps(analysis, indent=2))
"
                """,
                dependencies=["train-model"],
                timeout=120
            )
        ]
        
        # Execute tasks in order
        print("\n🔄 Executing data analysis pipeline...")
        for task in tasks:
            print(f"\n📋 Executing task: {task.id}")
            result = service.execute_task(task)
            
            if result.get("success"):
                print(f"✅ Task {task.id} completed successfully")
                if result.get("stdout"):
                    print(f"📄 Output: {result['stdout'][:200]}...")
            else:
                print(f"❌ Task {task.id} failed: {result.get('error', 'Unknown error')}")
                break
        
        # Show cost analysis
        print("\n💰 Cost Analysis:")
        cost_estimate = service.get_cost_estimate()
        print(f"   Total estimated cost: ${cost_estimate['total_cost']:.2f}")
        print(f"   Estimated hours: {cost_estimate['estimated_hours']:.1f}")
        
        for agent_name, cost_info in cost_estimate['agent_costs'].items():
            print(f"   {agent_name}: ${cost_info['total_cost']:.2f} (${cost_info['hourly_cost']:.2f}/hr)")
        
        # Show final results
        print("\n📊 Pipeline Results:")
        for task_id, result_info in service.results.items():
            task = result_info['task']
            result = result_info['result']
            print(f"   {task_id}: {'✅ Success' if result.get('success') else '❌ Failed'}")
        
        print("\n🎉 Data analysis pipeline completed!")
        
    except Exception as e:
        print(f"\n❌ Pipeline failed: {e}")
        logger.error(f"Pipeline error: {e}")
    
    finally:
        # Cleanup
        print("\n🧹 Cleaning up agents...")
        service.cleanup_all_agents()
        print("✅ Cleanup completed")

# ============================================================================
# Example: Agentic ChatGPT-like Service
# ============================================================================

def demo_agentic_chatgpt_service():
    """Demonstrate an agentic ChatGPT-like service"""
    print("\n🤖 OnMemOS v3 Agentic Service Demo: ChatGPT-like Service")
    print("=" * 60)
    
    client = OnMemOSClient()
    service = AgenticService(client, "chatgpt-agentic-demo")
    
    try:
        # Create specialized agents for different tasks
        agents = [
            AgentConfig(
                name="code-assistant",
                workspace_id="chatgpt-agentic-demo",
                namespace="chatgpt-agents",
                user_id="service-admin",
                cpu_size=CPUSize.LARGE,
                memory_size=MemorySize.LARGE,
                image_type=ImageType.PYTHON_ENTERPRISE,
                persistent_storage_gb=50,
                ttl_minutes=120
            ),
            AgentConfig(
                name="data-analyst",
                workspace_id="chatgpt-agentic-demo",
                namespace="chatgpt-agents",
                user_id="service-admin",
                cpu_size=CPUSize.MEDIUM,
                memory_size=MemorySize.LARGE,
                image_type=ImageType.PYTHON_PRO,
                persistent_storage_gb=30,
                ttl_minutes=90
            ),
            AgentConfig(
                name="ml-researcher",
                workspace_id="chatgpt-agentic-demo",
                namespace="chatgpt-agents",
                user_id="service-admin",
                cpu_size=CPUSize.XLARGE,
                memory_size=MemorySize.XLARGE,
                gpu_type=GPUType.T4,
                image_type=ImageType.PYTHON_ENTERPRISE,
                persistent_storage_gb=100,
                ttl_minutes=180
            )
        ]
        
        # Create agents
        print("\n📦 Creating ChatGPT-like agents...")
        for agent_config in agents:
            service.create_agent(agent_config)
        
        # Set up environments
        print("\n🔧 Setting up agent environments...")
        
        # Code assistant setup
        service.setup_agent_environment("code-assistant", [
            "pip install openai langchain python-dotenv",
            "mkdir -p /persist/code"
        ])
        
        # Data analyst setup
        service.setup_agent_environment("data-analyst", [
            "pip install pandas numpy matplotlib seaborn plotly",
            "mkdir -p /persist/analysis"
        ])
        
        # ML researcher setup
        service.setup_agent_environment("ml-researcher", [
            "pip install torch transformers datasets accelerate",
            "mkdir -p /persist/research"
        ])
        
        # Simulate user queries
        user_queries = [
            {
                "query": "Write a Python function to calculate fibonacci numbers",
                "agent": "code-assistant",
                "task_id": "fibonacci-code"
            },
            {
                "query": "Analyze this dataset: [1,2,3,4,5,6,7,8,9,10]",
                "agent": "data-analyst", 
                "task_id": "dataset-analysis"
            },
            {
                "query": "Fine-tune a BERT model for sentiment analysis",
                "agent": "ml-researcher",
                "task_id": "bert-finetuning"
            }
        ]
        
        # Process queries
        print("\n💬 Processing user queries...")
        for query_info in user_queries:
            print(f"\n📝 Query: {query_info['query']}")
            print(f"🤖 Agent: {query_info['agent']}")
            
            # Create task for the query
            task = AgentTask(
                id=query_info['task_id'],
                agent_name=query_info['agent'],
                command=f"""
                python -c "
import json
import time

# Simulate agent processing
print('Processing query: {query_info['query']}')
time.sleep(2)  # Simulate processing time

# Generate response based on agent type
if '{query_info['agent']}' == 'code-assistant':
    response = {{
        'type': 'code',
        'language': 'python',
        'code': 'def fibonacci(n):\\n    if n <= 1:\\n        return n\\n    return fibonacci(n-1) + fibonacci(n-2)',
        'explanation': 'This is a recursive implementation of the Fibonacci sequence.'
    }}
elif '{query_info['agent']}' == 'data-analyst':
    response = {{
        'type': 'analysis',
        'dataset': [1,2,3,4,5,6,7,8,9,10],
        'mean': 5.5,
        'median': 5.5,
        'std': 3.0276503540974917,
        'insights': 'The dataset shows a uniform distribution from 1 to 10.'
    }}
elif '{query_info['agent']}' == 'ml-researcher':
    response = {{
        'type': 'ml_task',
        'model': 'BERT',
        'task': 'sentiment_analysis',
        'steps': [
            'Load pre-trained BERT model',
            'Prepare sentiment dataset',
            'Fine-tune on sentiment data',
            'Evaluate on test set'
        ],
        'estimated_time': '2-3 hours'
    }}

print('Response generated successfully!')
print(json.dumps(response, indent=2))
"
                """,
                timeout=60
            )
            
            # Execute task
            result = service.execute_task(task)
            
            if result.get("success"):
                print(f"✅ Response generated successfully")
                if result.get("stdout"):
                    print(f"📄 Response: {result['stdout'][:300]}...")
            else:
                print(f"❌ Failed to generate response: {result.get('error', 'Unknown error')}")
        
        # Show cost analysis
        print("\n💰 Service Cost Analysis:")
        cost_estimate = service.get_cost_estimate()
        print(f"   Total cost for this session: ${cost_estimate['total_cost']:.2f}")
        
        print("\n🎉 ChatGPT-like agentic service demo completed!")
        
    except Exception as e:
        print(f"\n❌ Service failed: {e}")
        logger.error(f"Service error: {e}")
    
    finally:
        # Cleanup
        print("\n🧹 Cleaning up agents...")
        service.cleanup_all_agents()
        print("✅ Cleanup completed")

# ============================================================================
# Analysis: What's Missing for Production Agentic Services
# ============================================================================

def analyze_missing_features():
    """Analyze what features might be missing for production agentic services"""
    print("\n🔍 Analysis: Missing Features for Production Agentic Services")
    print("=" * 60)
    
    missing_features = {
        "Real-time Communication": {
            "WebSocket Support": "Real-time agent communication and streaming responses",
            "Message Queues": "Asynchronous task distribution and result collection",
            "Event-driven Architecture": "Reactive agent coordination"
        },
        "Advanced Orchestration": {
            "Workflow Engine": "Complex multi-step agent workflows",
            "Conditional Logic": "Dynamic agent selection based on task requirements",
            "Parallel Execution": "Multiple agents working simultaneously",
            "Error Recovery": "Automatic retry and fallback mechanisms"
        },
        "Security & Isolation": {
            "Agent Sandboxing": "Isolated execution environments",
            "Network Policies": "Controlled inter-agent communication",
            "Secrets Management": "Secure credential handling",
            "Audit Logging": "Comprehensive activity tracking"
        },
        "Scalability": {
            "Auto-scaling": "Dynamic agent creation based on load",
            "Load Balancing": "Distribute tasks across multiple agents",
            "Resource Pooling": "Shared resource management",
            "Horizontal Scaling": "Multi-region deployment"
        },
        "Monitoring & Observability": {
            "Real-time Metrics": "Agent performance and resource usage",
            "Distributed Tracing": "End-to-end request tracking",
            "Alerting": "Proactive issue detection",
            "Dashboard": "Visual monitoring interface"
        },
        "Cost Optimization": {
            "Predictive Scaling": "Anticipate resource needs",
            "Spot Instance Usage": "Cost-effective resource allocation",
            "Resource Scheduling": "Optimize agent placement",
            "Usage Analytics": "Detailed cost breakdown"
        },
        "User Experience": {
            "Interactive Sessions": "Real-time user-agent interaction",
            "Progress Tracking": "Task execution progress updates",
            "Result Caching": "Avoid redundant computations",
            "User Preferences": "Personalized agent configurations"
        }
    }
    
    for category, features in missing_features.items():
        print(f"\n📋 {category}:")
        for feature, description in features.items():
            print(f"   • {feature}: {description}")
    
    print("\n💡 Recommendations for Production:")
    print("   1. Implement WebSocket-based real-time communication")
    print("   2. Add workflow orchestration engine")
    print("   3. Enhance security with proper isolation")
    print("   4. Build comprehensive monitoring and alerting")
    print("   5. Implement cost optimization strategies")
    print("   6. Create user-friendly interfaces")

if __name__ == "__main__":
    print("🚀 OnMemOS v3 Agentic Service Demo")
    print("=" * 50)
    
    # Run demos
    demo_data_analysis_pipeline()
    demo_agentic_chatgpt_service()
    analyze_missing_features()
    
    print("\n🎉 Demo completed!")
    print("\n💡 Key Takeaways:")
    print("   ✅ Current SDK supports basic agent orchestration")
    print("   ✅ Context managers provide automatic cleanup")
    print("   ✅ Resource management and cost control available")
    print("   ⚠️  Missing real-time communication and advanced orchestration")
    print("   ⚠️  Need enhanced security and monitoring for production")
    print("   🚀 Foundation is solid for building agentic services!")
