# Payment & Billing System for OnMemOS v3

## 🎯 **Overview**

The OnMemOS v3 payment and billing system provides a complete infrastructure for managing user payments, credits, and billing across all platform services. It's designed to be **database-agnostic** with easy migration from MySQL to Supabase.

## 🏗️ **Architecture**

### **Database Interface (Abstract)**
- **Location**: `server/database/base.py`
- **Purpose**: Abstract base class defining all database operations
- **Benefits**: Easy migration between MySQL and Supabase

### **MySQL Implementation**
- **Location**: `server/database/mysql_client.py`
- **Purpose**: Complete MySQL implementation of the database interface
- **Features**: Async operations, connection pooling, automatic table creation

### **Factory Pattern**
- **Location**: `server/database/factory.py`
- **Purpose**: Creates database clients based on configuration
- **Configuration**: Environment variable `DATABASE_TYPE` (mysql/supabase)

## 💳 **Payment System Components**

### **1. User Management**
```python
# User types with different entitlements
class UserType(str, Enum):
    FREE = "free"        # Limited resources, $5 credit bonus
    PRO = "pro"          # More resources, better rates
    ENTERPRISE = "enterprise"  # High limits, best rates
    ADMIN = "admin"      # Unlimited access
```

### **2. Passport System (API Keys)**
```python
# Create passport for API access
passport = await db.create_passport(
    user_id, "My API Key", ["read", "write", "billing"]
)

# Validate passport
user_info = await db.validate_passport(passport_key)
```

### **3. Credit System**
- **Credit Balance**: Users have a credit balance for all operations
- **Credit Purchase**: Buy credits with real money (minimum $10)
- **Credit Usage**: Automatic deduction for sessions, storage, spaces
- **Transaction History**: Complete audit trail of all credit movements

### **4. Billing Types**
```python
class BillingType(str, Enum):
    CREDIT_PURCHASE = "credit_purchase"      # Buying credits
    STORAGE_CREATION = "storage_creation"    # Creating buckets/filestores
    SESSION_RUNTIME = "session_runtime"      # Running sessions
    SPACE_PURCHASE = "space_purchase"        # Buying pre-made spaces
```

## 💰 **Pricing Structure**

### **Session Pricing (Per Hour)**
| User Type | Small | Medium | Large | GPU |
|-----------|-------|--------|-------|-----|
| FREE      | $0.05 | $0.075 | $0.10 | $0.25 |
| PRO       | $0.025| $0.0375| $0.05 | $0.125 |
| ENTERPRISE| $0.01 | $0.015 | $0.02 | $0.05 |
| ADMIN     | $0.00 | $0.00  | $0.00 | $0.00 |

### **Storage Pricing (Per GB/Month)**
- **GCS Bucket**: $0.02/GB/month
- **Filestore PVC**: $0.17/GB/month

### **Space Pricing (One-time)**
- **ML Ready Environment**: $5.00 (50GB)
- **Data Science Toolkit**: $3.00 (30GB)
- **Web Development Stack**: $2.00 (20GB)
- **Research Environment**: $4.00 (40GB)

## 🗄️ **Database Schema**

### **Core Tables**

#### **Users Table**
```sql
CREATE TABLE users (
    id VARCHAR(255) PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255),
    user_type ENUM('free', 'pro', 'enterprise', 'admin') DEFAULT 'free',
    credits DECIMAL(10,2) DEFAULT 0.00,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
```

#### **Passports Table (API Keys)**
```sql
CREATE TABLE passports (
    id VARCHAR(255) PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    passport_key VARCHAR(255) UNIQUE NOT NULL,
    permissions JSON,
    is_active BOOLEAN DEFAULT TRUE,
    last_used TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
```

#### **Credit Transactions Table**
```sql
CREATE TABLE credit_transactions (
    id VARCHAR(255) PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    amount DECIMAL(10,2) NOT NULL,
    transaction_type ENUM('credit', 'debit') NOT NULL,
    source VARCHAR(255) NOT NULL,
    description TEXT,
    session_id VARCHAR(255) NULL,
    storage_resource_id VARCHAR(255) NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
```

#### **Session Billing Table**
```sql
CREATE TABLE session_billing (
    id VARCHAR(255) PRIMARY KEY,
    session_id VARCHAR(255) NOT NULL,
    user_id VARCHAR(255) NOT NULL,
    hourly_rate DECIMAL(10,4) NOT NULL,
    start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    end_time TIMESTAMP NULL,
    total_hours DECIMAL(10,4) NULL,
    total_cost DECIMAL(10,2) NULL,
    status ENUM('active', 'completed', 'cancelled') DEFAULT 'active',
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
```

#### **Spaces Table**
```sql
CREATE TABLE spaces (
    id VARCHAR(255) PRIMARY KEY,
    space_id VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    category VARCHAR(255) NOT NULL,
    size_gb INT NOT NULL,
    cost_usd DECIMAL(10,2) NOT NULL,
    is_public BOOLEAN DEFAULT TRUE,
    created_by VARCHAR(255) NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## 🔧 **Usage Examples**

### **1. User Registration with Infrastructure**
```python
from server.services.user_management import UserManagementService

user_service = UserManagementService()

# Create user with complete infrastructure
user_infrastructure = await user_service.create_user_with_infrastructure(
    email="user@example.com",
    name="John Doe",
    user_type=UserType.PRO
)

# This automatically:
# - Creates user record
# - Creates GCP service account
# - Sets up Workload Identity
# - Creates initial storage resources
```

### **2. API Key (Passport) Management**
```python
# Create API key
passport = await db.create_passport(
    user_id, "Production API Key", ["read", "write", "billing"]
)

# Validate API key
user_info = await db.validate_passport(passport["passport_key"])
if user_info:
    print(f"Authenticated user: {user_info['email']}")
    print(f"Credits: ${user_info['credits']:.2f}")
```

### **3. Credit Purchase**
```python
from server.services.billing_service import BillingService

billing_service = BillingService()

# Purchase credits
purchase = await billing_service.purchase_credits(
    user_id, 25.0, "stripe"
)

print(f"Purchased {purchase['total_credits']:.2f} credits for ${purchase['amount_usd']}")
```

### **4. Session Billing**
```python
# Start billing when session starts
billing_info = await billing_service.start_session_billing(
    session_id, user_id, "medium"
)

# ... session runs ...

# Stop billing when session ends
final_billing = await billing_service.stop_session_billing(session_id)
print(f"Session cost: ${final_billing['total_cost']:.4f}")
```

### **5. Space Purchase**
```python
# Get available spaces
spaces = await db.get_available_spaces()

# Purchase a space
user_space = await db.purchase_space(
    user_id, "ml-ready", workspace_id, "my-ml-dataset"
)

print(f"Purchased {user_space['instance_name']} for ${user_space['cost_usd']}")
```

### **6. Billing Summary**
```python
# Get comprehensive billing summary
summary = await billing_service.get_user_billing_summary(
    user_id,
    start_date=datetime.now() - timedelta(days=30),
    end_date=datetime.now()
)

print(f"Current balance: ${summary['current_balance']:.2f}")
print(f"Total spent: ${summary['total_spent']:.2f}")
```

## 🚀 **Integration with Session Creation**

### **Enhanced Session Creation with Billing**
```python
# When creating a session:
async def create_session_with_billing(session_request, passport_key):
    # 1. Validate passport
    user_info = await db.validate_passport(passport_key)
    if not user_info:
        raise ValueError("Invalid passport")
    
    # 2. Check credit balance
    estimated_cost = await billing_service.calculate_session_cost(
        user_info['user_id'], 
        session_request.ttl_minutes / 60.0,
        session_request.resource_tier
    )
    
    if not await billing_service.check_user_credit_balance(user_info['user_id'], estimated_cost):
        raise ValueError("Insufficient credits")
    
    # 3. Create session
    session = await create_session(session_request)
    
    # 4. Start billing
    await billing_service.start_session_billing(
        session.id, user_info['user_id'], session_request.resource_tier
    )
    
    return session
```

## 🔄 **Migration to Supabase**

### **Easy Migration Process**
1. **Create Supabase Client**: Implement `SupabaseClient` class
2. **Update Factory**: Add Supabase option to `DatabaseFactory`
3. **Environment Variable**: Set `DATABASE_TYPE=supabase`
4. **Data Migration**: Export MySQL data, import to Supabase

### **Supabase Implementation Structure**
```python
class SupabaseClient(DatabaseInterface):
    def __init__(self, supabase_url: str, supabase_key: str):
        self.supabase = create_client(supabase_url, supabase_key)
    
    async def create_user(self, user_id: str, email: str, ...):
        # Implement using Supabase client
        pass
    
    # ... implement all other methods
```

## 🧪 **Testing**

### **Run the Demo**
```bash
# Install dependencies
pip install -r requirements_database.txt

# Run the payment billing demo
python examples/payment_billing_demo.py
```

### **Demo Features**
- ✅ User creation with infrastructure
- ✅ Passport (API key) creation and validation
- ✅ Credit purchase and management
- ✅ Storage resource creation and cost calculation
- ✅ Session billing simulation
- ✅ Space purchasing
- ✅ Comprehensive billing summaries
- ✅ Transaction history tracking

## 🔐 **Security Features**

### **Passport Security**
- **Secure Generation**: Uses `secrets.token_urlsafe(32)` for API keys
- **Permission System**: Granular permissions per API key
- **Usage Tracking**: Last used timestamp for audit trails
- **Revocation**: Easy API key revocation

### **Credit Security**
- **Balance Validation**: Prevents overspending
- **Transaction Logging**: Complete audit trail
- **Atomic Operations**: Database transactions ensure consistency

### **Billing Security**
- **Rate Limiting**: Per-user hourly rate limits
- **Cost Calculation**: Transparent pricing calculations
- **Session Tracking**: Real-time session billing

## 📊 **Monitoring & Analytics**

### **Key Metrics**
- **Credit Usage**: Track credit consumption patterns
- **Session Costs**: Monitor session runtime costs
- **Storage Costs**: Track storage resource costs
- **User Behavior**: Analyze user spending patterns

### **Billing Reports**
```python
# Get user billing summary
summary = await billing_service.get_user_billing_summary(user_id)

# Get pricing information
pricing = await billing_service.get_pricing_info()

# Get credit history
history = await db.get_credit_history(user_id)
```

## 🎯 **Benefits**

### **For Users**
- **Transparent Pricing**: Clear cost structure
- **Credit System**: Flexible payment model
- **API Access**: Secure API key management
- **Usage Tracking**: Detailed billing history

### **For Platform**
- **Revenue Generation**: Multiple revenue streams
- **Resource Management**: Prevent abuse through limits
- **Scalability**: Database-agnostic architecture
- **Analytics**: Rich usage data for optimization

### **For Development**
- **Easy Migration**: Simple switch between databases
- **Comprehensive Testing**: Complete demo system
- **Modular Design**: Clean separation of concerns
- **Extensible**: Easy to add new billing types

## 🚀 **Next Steps**

1. **MySQL Setup**: Configure MySQL database
2. **Environment Variables**: Set up database configuration
3. **Run Demo**: Test the complete system
4. **Integration**: Integrate with existing session creation
5. **UI Development**: Build billing dashboard
6. **Payment Gateway**: Integrate Stripe/PayPal
7. **Supabase Migration**: When ready for production

This payment and billing system provides a **production-ready foundation** for monetizing OnMemOS v3 while maintaining **user isolation and system security** through the passport system and per-user service accounts.
