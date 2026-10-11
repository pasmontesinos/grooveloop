---
name: verify
description: "Verifies whether a deploy has degraded a service, comparing the new version against the previous one with written thresholds. Use for the verification of a merged slice, when checking a deploy, a dependency bump or a release, live or after the fact."
---

# grooveloop:verify

There is a hypothesis (this deploy) and a control (the previous version). That
sets it apart from anomaly detection, which learns a model of what is normal.
The pattern is called *automated canary analysis*.

It is a function of time: it takes an instant and a window. With the instant at
"now" it watches live; with a past instant it validates against history. The
procedure does not change.

This skill gives the method. The tools belong to each team: the queries to its
metrics, traces and logs systems arrive in the instruction, in the context
files or in the skills the repo's `verifier` profile declares.

## Non-negotiable rules

The verdict comes from written thresholds, never from your own judgment. The
skill collects the evidence, explains it and puts it in context; pass or fail
is set by the thresholds. Two runs on the same deploy must give the same result,
or the skill is useless.

There are three verdicts, not two: degrades, does not degrade and
inconclusive. Without enough signal it never passes.

**Without observability configured, do not ask and do not invent.** You run
with no human in the loop. If the instruction, the context files and the
profile skills do not say where the service metrics are, the verdict is
"inconclusive: the repo has no observability configured to verify the deploy",
and nothing else is judged.

Nothing that decides can depend on interactive credentials. The sources that
decide are the ones queried with no human intervention. A source that only
explains (for example, an error aggregator behind a login) does not change the
verdict when it is unavailable: the report says so.

The witness must be outside the library being verified. If the change updates
the instrumentation library, what it measures is part of what is verified. The
witness is an external component: the proxy, the ingress, the load balancer or
the broker.

Show the queries you run.

## Procedure

### 1. Locate the deploy

A change of deployed artifact (container image, package version, function
revision) is a deploy. The instant is when the first instance with the new
artifact appears, read from what the system actually runs and not from what
was requested to deploy.

The commit or merge date does not work: hours can pass between the merge and
the effect.

### 2. Discover the scope

A deploy is a new artifact, and its scope is every process that runs it: the
web service, the queue consumers and the scheduled jobs often share an
artifact. A failure in any of them fails the whole deploy.

Processes that do not adopt the new artifact are out of scope. Mention them
anyway: a process that does not move forward with the rest is a candidate to
break when the rest moves forward.

### 3. Split by version

Look in the metrics for the label that tells apart the version or revision of
each instance. Check that it is filled in before trusting it.

Two revisions are compared only if they belong to the same process. One
service can contain different long-running processes that are not versions of
each other.

### 4. Place the window in its two phases

During coexistence, both versions live the same minute with the same traffic:
it is the best possible control, with no time-of-day or volume bias. It usually
lasts a few minutes, and on low-traffic services it produces no data at all.

After that only the new version remains. There the reference is the previous
window, plus three or four earlier deploys as a measure of how much this
normally varies. Always normalize per unit of work.

Without coexistence, say so and work only with the second phase.

Coexistence does not work for the uncounted work criterion. The witness starts
before the application, so during those minutes it counts work the application
cannot record yet and the difference comes out inflated. That criterion is
always measured against the previous window.

### 5. Evaluate the criteria

Metrics are read in two opposite directions, and mixing them produces absurd
results. Work metrics are present and growing when all is well; their
disappearance or drop to zero is the alarm. Error metrics are absent when all
is well; their appearance is the alarm.

Hard criteria have no startup margin and act from second zero. Any of them
cuts: failures, restarts, consumption rate dropping to zero, uncounted work
fraction going up, new error metrics and new exception types.

Continuous criteria do have a startup margin, and they are relative and
normalized: latency, CPU per unit of work and memory. The margin applies only
here: if the system does not send traffic to an instance until it is ready, an
error in the first minute is a real error.

If the latency percentiles come only from the instrumentation the change
touches, they are weaker evidence. Say so in the report.

Informational criteria are listed and do not fail: routes, channels,
subscriptions or connectors that stop appearing.

Before declaring a value absent, widen the window. Low-frequency metric
families need a wider window than HTTP ones, and an absence in a short window
is usually sampling, not loss.

### 6. The uncounted work criterion

The application must keep counting the same proportion of the work it does.
It is the criterion that catches the silent failure, and it is measured
against an external witness.

The baseline is not zero: a structural difference always remains. The
criterion is relative to the service's own previous value, never to an
expected value.

Discard the health routes on both sides before comparing. They are not service
work, and they can reach the process without going through the witness.

The witness does not always see more than the application either. When the
difference comes out negative after discarding health routes, the criterion
measures nothing, and passing it is worse than not evaluating it: it stays
inconclusive.

A route deletion or rename does not trigger it, because its traffic also
disappears at the witness. Without a witness for that service, the criterion
stays inconclusive, never passed.

### 7. Verdict and report

Degrades when a hard criterion breaks in any process, or when a continuous one
goes out of margin with enough signal. Does not degrade when everything is
within margin and there was also enough signal to see it. Inconclusive when
there was little traffic, there is no witness, the reference does not work or
the repo has no observability configured.

Time is not symmetric: it can fail early, it can only pass at the end.

Always state the power: how many units of work of the new version were seen.
Without that figure, a "does not degrade" means nothing.

The report goes from conclusion to data, never the other way round. It opens
with the verdict in one line and the criterion that decides it. The
conclusions follow: what it means, which alarms were ruled out and with what
evidence, and what was left unevaluated. Only then the data: the deploy and
its two versions, the processes in scope, the coexistence and its duration,
and criterion by criterion the previous value, the new one, the margin and the
result. The informational criteria and the side findings close it.

Each interpretive statement carries its number next to it. A dismissal without
the data that supports it is not a dismissal, it is an opinion.

Write for someone who knows the system: full metric names, units, thresholds
and windows.

## Default thresholds

10-minute window. 2-minute startup margin, only for continuous criteria.
Minimum of 500 units of work to evaluate a continuous criterion.

Hard: failures and restarts at zero, consumption rate that does not drop to
zero, uncounted work with a 5-point margin over the previous value, and no new
error metric or exception type.

Continuous: p95 latency at 15%, CPU per unit of work at 20%, memory at 20%.

If the team configuration brings thresholds of its own for the service, those
rule. Without them, these, and the report says so.

## Calibrate

Before trusting the verdict, apply the method to twenty past deploys and count
how many it would have blocked. Adjust the margins with that figure, not with
intuition.
