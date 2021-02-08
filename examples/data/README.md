This folder contains data used for running the examples. When running examples which require input files, such as `csv_iter`, `SCARGO_LOCAL_MOUNT` must point to this folder.

This folder's directory structure mirrors the remote S3 folder structure for convenience [1].

## Running remote examples

Verify the data exists remotely by running `aws s3 ls s3://pq-dataxfer-tmp/testing/scargo-examples/`.

If it does not exist, upload it with `aws s3 sync testing/scargo-examples/ s3://pq-dataxfer-tmp/testing/scargo-examples/`.

If running the examples remotely, the outputs can be downloaded by running BLAH.

When not running examples, it is recommended you create your own folder `~/s3-data` and manage your workflow inputs/outputs from there.


[1] A future version of Scargo may enable mapping local folder structures to different remote structures if this is useful to enough people.
