from pebble import ProcessPool
manager = ""
add_dataset_processes= ""
select_queue = ""
select_wait_processes = ""
select_processes = ""
train_processes = ""
training_processes = ""
optimize_processes = ""
optimizing_processes = ""
auto_run_processes = ""
auto_waiting_processes = ""
fill_interval_process = ""
append_points_process = ""
update_dataset_processes = ""

task_proc_pool :ProcessPool = None
model_training_pool :ProcessPool = None

