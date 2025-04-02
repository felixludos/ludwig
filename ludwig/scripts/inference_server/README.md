Launch the vLLM server on the cluster interactively:
```
condor_submit_bid 257 -append 'request_cpus=16' -append 'request_memory=128GB' -append 'request_disk=200GB' -append 'request_gpus=2' -append 'requirements = (TARGET.CUDAGlobalMemoryMb > 50000) && (CUDADeviceName=="NVIDIA A100-SXM4-80GB")' -i

vllm serve "deepseek-ai/DeepSeek-R1-Distill-Llama-8B"
vllm serve "deepseek-ai/DeepSeek-R1-Distill-Llama-8B" --enable-reasoning --reasoning-parser deepseek_r1
```
or with a batch job:
```
joblog_dir=/home/mmordig/autoformalization/joblogs-inference
mkdir -p "$joblog_dir"
condor_submit_bid 257 -append "joblog_dir = $joblog_dir" /home/mmordig/autoformalization/code/ludwig/ludwig/scripts/inference_server/serve_llm.sub

# get 3 most recent files full name
jobfiles=$(find $joblog_dir -type f)
echo "Found job files: ${jobfiles}"
tail -f $jobfiles
# once the job is running
condor_q -l 16096070.0 | grep RemoteHost
```
Once the job has launched, you need to get the hostname!
Don't forget to delete the batch job when it is no longer needed.

Locally:
```
# define necessary functions for reaching it locally
function establish_port_forwarding() {
    local local_port=$1
    local remote_addr=$2
    echo Running ssh -x -f -N -n -L ${local_port}:${remote_addr} mpi
    ssh -x -f -N -n -L ${local_port}:${remote_addr} mpi
}
function kill_port_forwardings() {
    # Usage: kill_port_forwardings [<local_port>]
    
    # get PIDs of SSH tunnel processes
    pid_array=()
    while IFS= read -r line; do
        # Extract the PID from the ps output
        pid=$(echo "$line" | awk '{print $2}')
        pid_array+=("$pid")
    done < <(ps aux | grep "ssh -x -f -N -n -L $1")

    for pid in "${pid_array[@]}"; do
        echo "Terminating SSH tunnel with PID $pid"
        kill "$pid"
    done

    echo "All SSH tunnel processes terminated."
}
function check_reachable() {
    curl -o /dev/null -I --connect-timeout 5 "$1"
}

LLM_PORT=8001; compute_node=g136;
kill_port_forwardings $LLM_PORT; establish_port_forwarding $LLM_PORT $compute_node:8000
check_reachable http://0.0.0.0:$LLM_PORT/v1/models
python -m ludwig.scripts.inference_server.example_client
```

On the machine running the LLM inference server, you can run:
```
function check_reachable() {
    curl -o /dev/null -I --connect-timeout 5 "$1"
}
check_reachable http://$(hostname):8000/v1/models
# Note: check_reachable http://0.0.0.0:8000/v1/models does not work on the cluster!
LLM_PORT=8000 python -m ludwig.scripts.inference_server.example_client
```
