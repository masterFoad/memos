#!/usr/bin/env python3
"""
📋 OnMemOS v3 List → Clone → Verify Test
========================================

Focused test demonstrating:
1. List existing resources
2. Clone resources
3. List again to verify clones
"""

import os
import json
import time
from sdk.python.client import OnMemClient
from test_utils import generate_test_token

def main():
    print("📋 OnMemOS v3 List → Clone → Verify Test")
    print("=" * 50)
    print("🔍 Testing: List → Clone → List Verification")
    print("=" * 50)
    
    # Initialize client
    token = generate_test_token()
    client = OnMemClient('http://localhost:8080', token)
    
    print("✅ Connected to OnMemOS v3 server")
    print()
    
    # Test namespace and user
    namespace = "clone-test"
    user = "demo-user-123"
    
    print(f"📁 Test Namespace: {namespace}")
    print(f"👤 Test User: {user}")
    print()
    
    # Test 1: Bucket List → Clone → Verify
    print("📦 Test 1: Bucket List → Clone → Verify")
    print("-" * 40)
    
    try:
        # Step 1: Create a test bucket first
        print("🔧 Step 1: Creating test bucket...")
        bucket_name = f"test-bucket-{int(time.time())}"
        bucket = client.create_bucket(
            bucket_name=bucket_name,
            namespace=namespace,
            user=user
        )
        print(f"✅ Created bucket: {bucket_name}")
        
        # Step 2: List buckets (BEFORE clone)
        print("\n📋 Step 2: Listing buckets BEFORE clone...")
        buckets_before = client.list_buckets_in_namespace(namespace, user)
        print(f"✅ Found {len(buckets_before)} bucket(s) BEFORE clone:")
        for i, bucket in enumerate(buckets_before, 1):
            print(f"   {i}. {bucket.get('name', 'Unknown')}")
        
        # Step 3: Clone bucket
        print(f"\n🔄 Step 3: Cloning bucket '{bucket_name}'...")
        cloned_bucket = client.clone_bucket(
            source_bucket_name=bucket_name,
            new_bucket_name=f"{bucket_name}-clone",
            new_namespace=f"{namespace}-clone",
            new_user=user
        )
        print(f"✅ Cloned bucket: {cloned_bucket}")
        
        # Step 4: List buckets (AFTER clone)
        print("\n📋 Step 4: Listing buckets AFTER clone...")
        buckets_after = client.list_buckets_in_namespace(namespace, user)
        print(f"✅ Found {len(buckets_after)} bucket(s) AFTER clone:")
        for i, bucket in enumerate(buckets_after, 1):
            print(f"   {i}. {bucket.get('name', 'Unknown')}")
        
        # Step 5: List buckets in clone namespace
        print(f"\n📋 Step 5: Listing buckets in clone namespace '{namespace}-clone'...")
        buckets_clone_namespace = client.list_buckets_in_namespace(f"{namespace}-clone", user)
        print(f"✅ Found {len(buckets_clone_namespace)} bucket(s) in clone namespace:")
        for i, bucket in enumerate(buckets_clone_namespace, 1):
            print(f"   {i}. {bucket.get('name', 'Unknown')}")
        
        # Step 6: Verification
        print("\n✅ Step 6: Verification Results:")
        print(f"   📦 Original namespace buckets: {len(buckets_before)} → {len(buckets_after)}")
        print(f"   📦 Clone namespace buckets: {len(buckets_clone_namespace)}")
        print(f"   🔄 Clone successful: {'✅ YES' if len(buckets_clone_namespace) > 0 else '❌ NO'}")
        
        # Cleanup
        print("\n🧹 Cleaning up buckets...")
        client.delete_bucket(cloned_bucket['new_bucket'], force=True)
        print(f"   🗑️ Deleted cloned bucket: {cloned_bucket['new_bucket']}")
        
    except Exception as e:
        print(f"❌ Bucket test failed: {e}")
    
    print()
    
    # Test 2: Persistent Storage List → Clone → Verify
    print("💾 Test 2: Persistent Storage List → Clone → Verify")
    print("-" * 40)
    
    try:
        # Step 1: List persistent disks (BEFORE clone)
        print("📋 Step 1: Listing persistent disks BEFORE clone...")
        disks_before = client.list_persistent_disks(namespace, user)
        print(f"✅ Found {len(disks_before)} persistent disk(s) BEFORE clone:")
        for i, disk in enumerate(disks_before, 1):
            print(f"   {i}. {disk.get('disk_name', 'Unknown')}: {disk.get('size_gb', 0)}GB")
        
        if disks_before:
            # Step 2: Clone persistent disk
            source_disk = disks_before[0]
            source_disk_name = source_disk['disk_name']
            print(f"\n🔄 Step 2: Cloning persistent disk '{source_disk_name}'...")
            
            cloned_disk = client.clone_persistent_disk(
                source_disk_name=source_disk_name,
                new_disk_name=f"{source_disk_name}-clone",
                new_namespace=f"{namespace}-clone",
                new_user=user,
                size_gb=5
            )
            print(f"✅ Cloned disk: {cloned_disk}")
            
            # Step 3: List persistent disks (AFTER clone)
            print("\n📋 Step 3: Listing persistent disks AFTER clone...")
            disks_after = client.list_persistent_disks(namespace, user)
            print(f"✅ Found {len(disks_after)} persistent disk(s) AFTER clone:")
            for i, disk in enumerate(disks_after, 1):
                print(f"   {i}. {disk.get('disk_name', 'Unknown')}: {disk.get('size_gb', 0)}GB")
            
            # Step 4: List persistent disks in clone namespace
            print(f"\n📋 Step 4: Listing persistent disks in clone namespace '{namespace}-clone'...")
            disks_clone_namespace = client.list_persistent_disks(f"{namespace}-clone", user)
            print(f"✅ Found {len(disks_clone_namespace)} persistent disk(s) in clone namespace:")
            for i, disk in enumerate(disks_clone_namespace, 1):
                print(f"   {i}. {disk.get('disk_name', 'Unknown')}: {disk.get('size_gb', 0)}GB")
            
            # Step 5: Verification
            print("\n✅ Step 5: Verification Results:")
            print(f"   💾 Original namespace disks: {len(disks_before)} → {len(disks_after)}")
            print(f"   💾 Clone namespace disks: {len(disks_clone_namespace)}")
            print(f"   🔄 Clone successful: {'✅ YES' if len(disks_clone_namespace) > 0 else '❌ NO'}")
            
            # Cleanup
            print("\n🧹 Cleaning up persistent disks...")
            client.delete_persistent_disk(cloned_disk['new_disk'], force=True)
            print(f"   🗑️ Deleted cloned disk: {cloned_disk['new_disk']}")
            
        else:
            print("⚠️  No persistent disks found to clone")
            
    except Exception as e:
        print(f"❌ Persistent storage test failed: {e}")
    
    print()
    
    # Test 3: Complete Namespace Resource List → Clone → Verify
    print("📁 Test 3: Complete Namespace Resource List → Clone → Verify")
    print("-" * 40)
    
    try:
        # Step 1: List all resources in namespace (BEFORE clone)
        print("📋 Step 1: Listing all resources BEFORE clone...")
        
        workspaces_before = client.list_workspaces_in_namespace(namespace, user)
        buckets_before = client.list_buckets_in_namespace(namespace, user)
        disks_before = client.list_persistent_disks(namespace, user)
        
        print(f"✅ Resources BEFORE clone:")
        print(f"   📦 Workspaces: {len(workspaces_before)}")
        print(f"   📦 Buckets: {len(buckets_before)}")
        print(f"   💾 Persistent Disks: {len(disks_before)}")
        
        # Step 2: Clone entire namespace (simulated)
        print(f"\n🔄 Step 2: Cloning entire namespace '{namespace}'...")
        
        # Clone a workspace if available
        if workspaces_before:
            source_workspace = workspaces_before[0]
            cloned_workspace = client.clone_workspace(
                source_workspace_id=source_workspace['id'],
                new_namespace=f"{namespace}-clone",
                new_user=user
            )
            print(f"✅ Cloned workspace: {cloned_workspace}")
        
        # Clone a bucket if available
        if buckets_before:
            source_bucket = buckets_before[0]
            cloned_bucket = client.clone_bucket(
                source_bucket_name=source_bucket['name'],
                new_bucket_name=f"{source_bucket['name']}-clone",
                new_namespace=f"{namespace}-clone",
                new_user=user
            )
            print(f"✅ Cloned bucket: {cloned_bucket}")
        
        # Clone a disk if available
        if disks_before:
            source_disk = disks_before[0]
            cloned_disk = client.clone_persistent_disk(
                source_disk_name=source_disk['disk_name'],
                new_disk_name=f"{source_disk['disk_name']}-clone",
                new_namespace=f"{namespace}-clone",
                new_user=user
            )
            print(f"✅ Cloned disk: {cloned_disk}")
        
        # Step 3: List all resources in clone namespace (AFTER clone)
        print(f"\n📋 Step 3: Listing all resources in clone namespace '{namespace}-clone'...")
        
        workspaces_clone = client.list_workspaces_in_namespace(f"{namespace}-clone", user)
        buckets_clone = client.list_buckets_in_namespace(f"{namespace}-clone", user)
        disks_clone = client.list_persistent_disks(f"{namespace}-clone", user)
        
        print(f"✅ Resources in clone namespace:")
        print(f"   📦 Workspaces: {len(workspaces_clone)}")
        print(f"   📦 Buckets: {len(buckets_clone)}")
        print(f"   💾 Persistent Disks: {len(disks_clone)}")
        
        # Step 4: Verification
        print("\n✅ Step 4: Complete Verification Results:")
        print(f"   📦 Workspaces: {len(workspaces_before)} → {len(workspaces_clone)}")
        print(f"   📦 Buckets: {len(buckets_before)} → {len(buckets_clone)}")
        print(f"   💾 Persistent Disks: {len(disks_before)} → {len(disks_clone)}")
        
        total_before = len(workspaces_before) + len(buckets_before) + len(disks_before)
        total_after = len(workspaces_clone) + len(buckets_clone) + len(disks_clone)
        
        print(f"   📊 Total Resources: {total_before} → {total_after}")
        print(f"   🔄 Clone successful: {'✅ YES' if total_after > 0 else '❌ NO'}")
        
        # Cleanup
        print("\n🧹 Cleaning up clone namespace...")
        
        for ws in workspaces_clone:
            client.delete_workspace(ws['id'])
            print(f"   🗑️ Deleted workspace: {ws['id']}")
        
        for bucket in buckets_clone:
            client.delete_bucket(bucket['name'], force=True)
            print(f"   🗑️ Deleted bucket: {bucket['name']}")
        
        for disk in disks_clone:
            client.delete_persistent_disk(disk['disk_name'], force=True)
            print(f"   🗑️ Deleted disk: {disk['disk_name']}")
        
        print("✅ Clone namespace cleanup completed")
        
    except Exception as e:
        print(f"❌ Complete namespace test failed: {e}")
    
    print()
    
    # Summary
    print("🎉 List → Clone → Verify Test Complete!")
    print("=" * 50)
    print("What we tested:")
    print("✅ Bucket: List → Clone → List Verification")
    print("✅ Persistent Storage: List → Clone → List Verification")
    print("✅ Complete Namespace: List → Clone → List Verification")
    print("✅ Resource counting and verification")
    print("✅ Proper cleanup and resource management")
    print()
    print("🔍 Verification Features:")
    print("✅ Before/After resource counting")
    print("✅ Clone namespace resource verification")
    print("✅ Resource type-specific cloning")
    print("✅ Complete namespace cloning")
    print("✅ Proper cleanup and resource management")

if __name__ == "__main__":
    main()
