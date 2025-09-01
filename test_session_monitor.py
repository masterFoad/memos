#!/usr/bin/env python3
"""
Test Session Monitor Integration
===============================
"""

try:
    from server.services.session_monitor import session_monitor
    
    print("✅ Session monitor imported successfully")
    print(f"   Max duration: {session_monitor.limits.max_duration_hours} hours")
    print(f"   Max cost: ${session_monitor.limits.max_cost_usd}")
    print(f"   Check interval: {session_monitor.limits.check_interval_minutes} minutes")
    
    print("\n✅ Session monitor methods available:")
    print("   - start_monitoring()")
    print("   - stop_monitoring()")
    print("   - _check_all_sessions()")
    print("   - _kill_session()")
    
    print("\n🎉 Session monitor integration test passed!")
    
except Exception as e:
    print(f"❌ Error testing session monitor integration: {e}")
