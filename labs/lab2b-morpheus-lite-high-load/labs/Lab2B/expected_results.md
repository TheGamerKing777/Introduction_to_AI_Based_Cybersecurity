# Expected Results

Results vary by machine. Students should not be graded against exact values.

A healthy normal run usually shows similar generator, detector, and orchestrator throughput, a backlog that returns to zero, and end-to-end latency dominated by relatively small queue and processing delays.

A burst run may show a temporary gap between arrival and processing rates, followed by queue drainage.

Sustained and attack-surge runs may show persistent backlog, utilization near configured warning thresholds, and increasing queue-wait latency. A high event count alone does not prove overload; students must use throughput, backlog, utilization, and latency together.
