#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""
@author: s0nik42
"""
# veolia-idf
# Copyright (C) 2019 Julien NOEL
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
#
VERSION="v0.1"

#
# CONFIG VARIABLES // OPTIONAL THEY ARE NORMALLY AUTODETECTED
#
MINER_URL = ""
MINER_TOKEN = ""
DAEMON_URL = ""
DAEMON_TOKEN = ""

#
# DO NOT EDIT BELOW
#
from urllib import request
from urllib.parse import urlparse
from pathlib import Path
import json
import time

# Start execution time mesurement
start_time = time.time()

# SET DEFAULT VALUES
if MINER_URL == '': MINER_URL = "http://127.0.0.1:2345/rpc/v0"
if DAEMON_URL == '': DAEMON_URL = "http://127.0.0.1:1234/rpc/v0"
if MINER_TOKEN == '': 
    with open(str(Path.home()) + "/.lotusminer/token", "r") as text_file:
        MINER_TOKEN = text_file.read()
if DAEMON_TOKEN == '': 
    with open(str(Path.home()) + "/.lotus/token", "r") as text_file:
        DAEMON_TOKEN = text_file.read()

# REQUEST FUNCTIONS
def daemon_get_json(method, params):
    return(get_json(DAEMON_URL,DAEMON_TOKEN,method, params))

def miner_get_json(method, params):
    return(get_json(MINER_URL,MINER_TOKEN,method, params))

def get_json(url,token,method, params):
    jsondata = json.dumps({ "jsonrpc": "2.0", "method": "Filecoin." + method, "params": params, "id": 3 }).encode("utf8")
    req = request.Request(url)
    req.add_header('Authorization', 'Bearer ' + token )
    req.add_header("Content-Type","application/json")

    res = request.urlopen(req, jsondata).read()
    page = res.decode("utf8")

    # parse json object
    obj = json.loads(page)

    # output some object attributes
    return(obj)

# EXECUTION TIME MEASUREMENT FINCTION
collector_start_time = False
def checkpoint(collector_name):
    global collector_start_time
    if not collector_start_time:
        collector_start_time = start_time
        print("# HELP test_lotus_miner_scrape_duration_seconds execution time of the different collectors")
        print("# TYPE test_lotus_miner_scrape_duration_seconds gauge")
    print(f'test_lotus_miner_scrape_duration_seconds{{ collector="{ collector_name}" }} {time.time() - collector_start_time}')
    collector_start_time = time.time()

# RETRIEVE MINER ID
actoraddress = miner_get_json("ActorAddress", [])
miner_id = actoraddress['result']

# RETRIEVE TIPSET + CHAINHEAD
chainhead = daemon_get_json("ChainHead", [])
tipsetkey = chainhead["result"]["Cids"]
print("# HELP test_lotus_daemon_height return current height")
print("# TYPE test_lotus_daemon_height counter")
print(f'test_lotus_daemon_height {{ miner_id="{miner_id}" }} {chainhead["result"]["Height"]}')
checkpoint("ChainHead")

# GENERATE CHAIN SYNC STATUS
print("# HELP test_lotus_daemon_chain_sync_diff return daemon sync height diff with chainhead for each daemon worker")
print("# TYPE test_lotus_daemon_chain_sync_diff  gauge")
print("# HELP test_lotus_daemon_chain_sync_status return daemon sync status with chainhead for each daemon worker")
print("# TYPE test_lotus_daemon_chain_sync_status  gauge")
sync_status = daemon_get_json("SyncState",[])
for worker in sync_status["result"]["ActiveSyncs"]:
    print(f'test_lotus_daemon_chain_sync_diff {{ miner_id="{ miner_id }", worker_id="{ sync_status["result"]["ActiveSyncs"].index(worker) }" }} { worker["Target"]["Height"] - worker["Base"]["Height"]  }')
    print(f'test_lotus_daemon_chain_sync_status {{ miner_id="{ miner_id }", worker_id="{ sync_status["result"]["ActiveSyncs"].index(worker) }" }} { worker["Stage"]  }')
checkpoint("ChainSync")

# GENERATE MINER INFO
miner_version = miner_get_json("Version", [])
checkpoint("Miner")

# RETRIEVE MAIN ADDRESSES
daemon_stats = daemon_get_json("StateMinerInfo",[miner_id,tipsetkey])
miner_owner = daemon_stats["result"]["Owner"]
miner_worker = daemon_stats["result"]["Worker"]
miner_control0 = daemon_stats["result"]["ControlAddresses"][0]
miner_owner_addr = daemon_get_json("StateAccountKey",[miner_owner,tipsetkey])["result"]
miner_worker_addr = daemon_get_json("StateAccountKey",[miner_worker,tipsetkey])["result"]
miner_control0_addr = daemon_get_json("StateAccountKey",[miner_control0,tipsetkey])["result"]

print("# HELP test_lotus_miner_info lotus miner information like adress version etc")
print("# TYPE test_lotus_miner_info gauge")
print(f'test_lotus_miner_info {{ miner_id = "{miner_id}", version="{ miner_version["result"]["Version"] }", owner="{ miner_owner }", owner_addr="{ miner_owner_addr }", worker="{ miner_worker }", worker_addr="{ miner_worker_addr }", control0="{ miner_control0 }", control0_addr="{ miner_control0_addr }" }} 1' )
checkpoint("StateMinerInfo")

# GENERATE DAEMON INFO
daemon_network = daemon_get_json("StateNetworkName",[])
daemon_version= daemon_get_json("Version", [])
print("# HELP test_lotus_daemon_info lotus daemon information like adress version etc")
print("# TYPE test_lotus_daemon_info gauge")
print(f'test_lotus_daemon_info {{ miner_id = "{miner_id}", version="{ daemon_version["result"]["Version"] }", network="{ daemon_network["result"] }"}} 1' )
checkpoint("Daemon")

# GENERATE WALLET + LOCKED FUNDS BALANCES
walletlist = daemon_get_json("WalletList", [])
print("# HELP test_lotus_wallet_balance return wallet balance")
print("# TYPE test_lotus_wallet_balance gauge")
for (addr) in walletlist["result"]:
    balance=daemon_get_json("WalletBalance", [addr])
    short=addr[0:5] + "..." + addr[-5:]
    print(f'test_lotus_wallet_balance {{ miner_id="{miner_id}", address="{ addr }", short="{ short }" }} { int(balance["result"])/1000000000000000000 }')

# Add miner balance :
miner_balance_available = daemon_get_json("StateMinerAvailableBalance",[miner_id,tipsetkey])
print(f'test_lotus_wallet_balance {{ miner_id="{miner_id}", address="{ miner_id }", short="{ miner_id }" }} { int(miner_balance_available["result"])/1000000000000000000 }')

# Retrieve locked funds balance
locked_funds = daemon_get_json("StateReadState",[miner_id,tipsetkey])
print("# HELP test_lotus_wallet_locked_balance return miner wallet locked funds")
print("# TYPE test_lotus_wallet_locked_balance gauge")
for i in ["PreCommitDeposits", "LockedFunds", "FeeDebt", "InitialPledge"]:
    print(f'test_lotus_wallet_locked_balance {{ miner_id="{miner_id}", address="{ miner_id }", locked_type ="{ i }" }} { int(locked_funds["result"]["State"][i])/1000000000000000000 }')
checkpoint("Balances")

# GENERATE POWER
# XXX ADD COMMITTED POWER
powerlist = daemon_get_json("StateMinerPower",[miner_id, tipsetkey])
print("# HELP test_lotus_power return miner power")
print("# TYPE test_lotus_power gauge")
for (minerpower) in powerlist["result"]["MinerPower"]:
        print(f'test_lotus_power {{ miner_id="{miner_id}", scope="miner", powertype="{ minerpower }" }} { powerlist["result"]["MinerPower"][minerpower] }')
for (totalpower) in powerlist["result"]["TotalPower"]:
        print(f'test_lotus_power {{ miner_id="{miner_id}", scope="network", powertype="{ totalpower }" }} { powerlist["result"]["TotalPower"][totalpower] }')

# Mining eligibility
print("# HELP test_lotus_power_mining_eligibility return miner mining eligibility")
print("# TYPE test_lotus_power_mining_eligibility gauge")
baseInfo = daemon_get_json("MinerGetBaseInfo",[miner_id,chainhead["result"]["Height"],tipsetkey])
if baseInfo["result"]["EligibleForMining"]:
    eligibility=1
else:
    eligibility=0
print(f'test_lotus_power_mining_eligibility {{ miner_id="{miner_id}" }} { eligibility }')
checkpoint("Power")

# GENERATE MPOOL 
mpoolpending = daemon_get_json("MpoolPending",[tipsetkey])
print("# HELP test_lotus_mpool_total return number of message pending in mpool")
print("# TYPE test_lotus_mpool_total gauge")
print("# HELP test_lotus_mpool_local_total return total number in mpool comming from local adresses")
print("# TYPE test_lotus_power_local_total gauge")
print("# HELP test_lotus_mpool_local_message local message details")
print("# TYPE test_lotus_mpool_local_message gauge")
mpool_total=0
mpool_local_total=0
for (message) in mpoolpending["result"]:
    mpool_total += 1
    frm = message["Message"]["From"]
    if frm in walletlist["result"]:
        mpool_local_total += 1
        if frm == miner_owner_addr:
            display_addr="owner"
        elif frm == miner_worker_addr:
            display_addr="worker"
        elif frm == miner_control0_addr:
            display_addr="control0"
        elif frm != miner_id:
            display_addr = frm[0:5] + "..." + frm[-5:]
        print(f'test_lotus_mpool_local_message {{ miner_id="{miner_id}", from="{ display_addr }", to="{ message["Message"]["To"] }", nonce="{ message["Message"]["Nonce"] }", value="{ message["Message"]["Value"] }", gaslimit="{ message["Message"]["GasLimit"] }", gasfeecap="{ message["Message"]["GasFeeCap"] }", gaspremium="{ message["Message"]["GasPremium"] }", method="{ message["Message"]["Method"] }" }} 1')

print(f'test_lotus_mpool_total {{ miner_id="{miner_id}" }} { mpool_total }')
print(f'test_lotus_mpool_local_total {{ miner_id="{miner_id}" }} { mpool_local_total }')
checkpoint("MPool")

# GENERATE NET_PEERS
print("# HELP test_lotus_netpeers_total return number netpeers")
print("# TYPE test_lotus_netpeers_total gauge")
daemon_netpeers = daemon_get_json("NetPeers",[])
daemon_netpeers_total = 0
for (peers) in daemon_netpeers["result"]:
    daemon_netpeers_total += 1
print(f'test_lotus_netpeers_total {{ miner_id="{miner_id}", service="daemon" }} { daemon_netpeers_total }')
miner_netpeers = miner_get_json("NetPeers",[])
miner_netpeers_total = 0
for (peers) in miner_netpeers["result"]:
    miner_netpeers_total += 1
print(f'test_lotus_netpeers_total {{ miner_id="{miner_id}", service="miner" }} { miner_netpeers_total }')
checkpoint("NetPeers")

# GENERATE NETSTATS XXX Verfier la qualité des stats ... lotus net, API et Grafana sont tous differents
print("# HELP test_lotus_net_protocol_in return input net per protocol")
print("# TYPE test_lotus_net_protocol_in counter")
print("# HELP test_lotus_net_protocol_out return output per protocol net")
print("# TYPE test_lotus_net_protocol_out counter")
protocols_list = daemon_get_json("NetBandwidthStatsByProtocol",[])
for (protocols) in protocols_list["result"]:
    print(f'test_lotus_net_protocol_in {{ miner_id="{miner_id}", service="daemon", protocols="{ protocols  }" }} { protocols_list["result"][protocols]["TotalIn"] }')
    print(f'test_lotus_net_protocol_out {{ miner_id="{miner_id}", service="daemon", protocols="{ protocols  }" }} { protocols_list["result"][protocols]["TotalOut"] }')

protocols_list = miner_get_json("NetBandwidthStatsByProtocol",[])
for (protocols) in protocols_list["result"]:
    print(f'test_lotus_net_protocol_in {{ miner_id="{miner_id}", service="miner", protocols="{ protocols  }" }} { protocols_list["result"][protocols]["TotalIn"] }')
    print(f'test_lotus_net_protocol_out {{ miner_id="{miner_id}", service="miner", protocols="{ protocols  }" }} { protocols_list["result"][protocols]["TotalOut"] }')

print("# HELP test_lotus_net_total_in return input net")
print("# TYPE test_lotus_net_total_in counter")
print("# HELP test_lotus_net_total_out return output net")
print("# TYPE test_lotus_net_total_out counter")
net_list = miner_get_json("NetBandwidthStats",[])
print(f'test_lotus_net_total_in {{ miner_id="{miner_id}", service="miner"  }} { net_list["result"]["TotalIn"] }')
print(f'test_lotus_net_total_out {{ miner_id="{miner_id}", service="miner" }} { net_list["result"]["TotalOut"] }')

net_list = daemon_get_json("NetBandwidthStats",[])
print(f'test_lotus_net_total_in {{ miner_id="{miner_id}", service="daemon"  }} { net_list["result"]["TotalIn"] }')
print(f'test_lotus_net_total_out {{ miner_id="{miner_id}", service="daemon" }} { net_list["result"]["TotalOut"] }')
checkpoint("NetBandwidth")

# GENERATE WORKER INFOS 
workerstats= miner_get_json("WorkerStats", [])
print("# HELP test_lotus_miner_worker_id All lotus worker information prfer to use workername than workerid which is changing at each restart")
print("# TYPE test_lotus_miner_worker_id gauge")
print("# HELP test_lotus_miner_worker_mem_physical_used worker minimal memory used")
print("# TYPE test_lotus_miner_worker_mem_physical_used gauge")
print("# HELP test_lotus_miner_worker_mem_vmem_used worker maximum memory used")
print("# TYPE test_lotus_miner_worker_mem_vmem_used gauge")
print("# HELP test_lotus_miner_worker_mem_reserved worker memory reserved by lotus")
print("# TYPE test_lotus_miner_worker_mem_reserved gauge")
print("# HELP test_lotus_miner_worker_gpu_used is the GPU used by lotus")
print("# TYPE test_lotus_miner_worker_gpu_used gauge")
print("# HELP test_lotus_miner_worker_cpu_used number of CPU used by lotus")
print("# TYPE test_lotus_miner_worker_cpu_used gauge")
print("# HELP test_lotus_miner_worker_cpu number of CPU")
print("# TYPE test_lotus_miner_worker_cpu gauge")
print("# HELP test_lotus_miner_worker_gpu number of GPU")
print("# TYPE test_lotus_miner_worker_gpu gauge")
print("# HELP test_lotus_miner_worker_mem_physical server RAM")
print("# TYPE test_lotus_miner_worker_mem_physical gauge")
print("# HELP test_lotus_miner_worker_mem_swap server SWAP")
print("# TYPE test_lotus_miner_worker_mem_swap gauge")
for (wrkid,val) in workerstats["result"].items():
    info=val["Info"]
    worker_name=info["Hostname"]
    mem_physical=info["Resources"]["MemPhysical"]
    mem_swap=info["Resources"]["MemSwap"]
    mem_reserved=info["Resources"]["MemReserved"]
    cpus=info["Resources"]["CPUs"]
    gpus=len(info["Resources"]["GPUs"])
    mem_used_min=val["MemUsedMin"]
    mem_used_max=val["MemUsedMax"]
    if val["GpuUsed"]:
        gpu_used=1
    else:
        gpu_used=0
    cpu_used=val["CpuUse"]
    print(f'test_lotus_miner_worker_id {{ miner_id="{miner_id}", worker_name="{worker_name}" }} { wrkid }')
    print(f'test_lotus_miner_worker_cpu {{ miner_id="{miner_id}", worker_name="{worker_name}" }} { cpus }')
    print(f'test_lotus_miner_worker_gpu {{ miner_id="{miner_id}", worker_name="{worker_name}" }} { gpus }')
    print(f'test_lotus_miner_worker_mem_physical {{ miner_id="{miner_id}", worker_name="{worker_name}" }} { mem_physical }')
    print(f'test_lotus_miner_worker_mem_swap {{ miner_id="{miner_id}", worker_name="{worker_name}" }} { mem_swap }')
    print(f'test_lotus_miner_worker_mem_physical_used {{ miner_id="{miner_id}", worker_name="{worker_name}" }} {mem_used_min}')
    print(f'test_lotus_miner_worker_mem_vmem_used {{ miner_id="{miner_id}", worker_name="{worker_name}" }} {mem_used_max}')
    print(f'test_lotus_miner_worker_mem_reserved {{ miner_id="{miner_id}", worker_name="{worker_name}" }} {mem_reserved}')
    print(f'test_lotus_miner_worker_gpu_used {{ miner_id="{miner_id}", worker_name="{worker_name}" }} {gpu_used}')
    print(f'test_lotus_miner_worker_cpu_used {{ miner_id="{miner_id}", worker_name="{worker_name}" }} {cpu_used}')
checkpoint("Workers")

# GENERATE JOB INFOS
workerjobs = miner_get_json("WorkerJobs", [])
print("# HELP test_lotus_miner_worker_job status of each individual job running on the workers. Value is the duration")
print("# TYPE test_lotus_miner_worker_job gauge")
for (wrk, job_list) in workerjobs["result"].items():
    for (job) in job_list:
        jobid= job['ID']
        sector=str(job['Sector']['Number'])
        worker=workerstats["result"][wrk]["Info"]["Hostname"]
        task=str(job['Task'])
        start=str(job['Start'])
        runwait=str(job['RunWait'])
        job_start_time=time.mktime(time.strptime(start.split('.')[0], '%Y-%m-%dT%H:%M:%S'))
        print(f'test_lotus_miner_worker_job {{ miner_id="{miner_id}", job_id="{jobid}", worker="{worker}", task="{task}", sector="{sector}", start="{start}", runwait="{runwait}" }} { start_time - job_start_time }')
checkpoint("Jobs")

# GENERATE JOB SCHEDDIAG
scheddiag  = miner_get_json("SealingSchedDiag", [])

for (sched, req_list) in scheddiag["result"].items():
    if(sched == "Requests" and req_list != None):
        for (req) in req_list:
            sector=req["Sector"]["Number"]
            task=req["TaskType"]
            priority=req["Priority"]
            print(f'test_lotus_miner_worker_job {{ miner_id="{miner_id}", job_id="", worker="", task="{task}", sector="{sector}", start="", runwait="99" }} 0')
checkpoint("SchedDiag")

# GENERATE SECTORS
print("# HELP test_lotus_miner_sector_state sector state")
print("# TYPE test_lotus_miner_sector_state gauge")
sector_list = miner_get_json("SectorsList",[])
#sectors_counters = {}
# remove duplicate (bug)
unique_sector_list = set(sector_list["result"])
for sector in unique_sector_list:
    detail = miner_get_json("SectorsStatus", [sector, False])
    print(f'test_lotus_miner_sector_state {{ miner_id="{miner_id}", sector_id="{ sector }", state="{ detail["result"]["State"] }" }} 1')
checkpoint("Sectors")

# GENERATE STORAGE INFO
print("# HELP test_lotus_miner_storage_info get storage info state")
print("# TYPE test_lotus_miner_storage_info gauge")
print("# HELP test_lotus_miner_storage_capacity get storage total capacity")
print("# TYPE test_lotus_miner_storage_capacity gauge")
print("# HELP test_lotus_miner_storage_available get storage available capacity")
print("# TYPE test_lotus_miner_storage_available gauge")
print("# HELP test_lotus_miner_storage_reserved get storage reserved capacity")
print("# TYPE test_lotus_miner_storage_reserved  gauge")
storage_list = miner_get_json("StorageList",[])
storage_local_list = miner_get_json("StorageLocal",[])
for storage in storage_list["result"].keys():
    storage_info = miner_get_json("StorageInfo",[storage])
    storage_stat = miner_get_json("StorageStat",[storage])
    if storage in storage_local_list["result"].keys():
        storage_path=storage_local_list["result"][storage]
    else:
        storage_path=''
    storage_id = storage_info["result"]["ID"]
    storage_url = urlparse(storage_info["result"]["URLs"][0])
    storage_url_ip =  storage_url.hostname 
    storage_url_port = storage_url.port
    storage_weight = storage_info["result"]["Weight"]
    storage_canseal = storage_info["result"]["CanSeal"]
    storage_canstore = storage_info["result"]["CanStore"]
    storage_capacity = storage_stat["result"]["Capacity"]
    storage_available = storage_stat["result"]["Available"]
    storage_reserved = storage_stat["result"]["Reserved"]
    print(f'test_lotus_miner_storage_info {{ miner_id="{miner_id}", storage_id="{ storage_id }", storage_url="{ storage_info["result"]["URLs"][0] }", storage_url_ip="{ storage_url_ip }", storage_url_port="{ storage_url_port }", weight="{ storage_weight }", canseal="{ storage_canseal }", canstore="{ storage_canstore }", path="{ storage_path }" }} 1')
    print(f'test_lotus_miner_storage_capacity {{ miner_id="{miner_id}", storage_id="{ storage_id }" }} { storage_capacity }')
    print(f'test_lotus_miner_storage_available {{ miner_id="{miner_id}", storage_id="{ storage_id }" }} { storage_available }')
    print(f'test_lotus_miner_storage_reserved {{ miner_id="{miner_id}", storage_id="{ storage_id }" }} { storage_reserved }')
checkpoint("Storage")

# GENERATE SCRAPE TIME
print(f'test_lotus_miner_scrape_duration_seconds {{ collector="All" }} {time.time() - start_time}')
# XXX TODO
# XXX CAlculate Block win rate mining/every ...
# print(daemon_get_json("StateMinerProvingDeadline",[miner_id,tipsetkey]))
# XXX rajouter les errors de sectors et de deadlines
#print(daemon_get_json("StateMinerFaults",[miner_id,tipsetkey]))
# GAs price
#print(daemon_get_json("StateMinerSectorCount",[miner_id,tipsetkey]))
# {'jsonrpc': '2.0', 'result': {'Live': 624, 'Active': 594, 'Faulty': 0}, 'id': 3}
# SectorsList :: List of sectors without info
# XXX Display SectorGetSealDelay / XXX Display sealing Sectors and details
# Winning blocks 
# WaitDeal (list of deals/ Since / SealWaitingTime)
# XXX get-ask // Assek deals
