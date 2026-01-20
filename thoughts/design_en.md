I want to implement task recursion using skills in Claude Code, in order to achieve more complex decision graphs.

After tasks are broken down, the content exposed at each step should be just right.

For example:

- A skill can contain multiple complex steps (decision graph)
- Or a skill can recursively call another skill to drive the entire task execution

I prefer a skill containing multiple complex steps (decision graph).


One approach was tested but the results were unsatisfactory.

In skills, one SKILL.md contains an index of multiple md files


SKILL.md:
```
---
skills header
---

1.md : <subflow description>
2.md : <subflow description>
3.md : <subflow description>
...
```

1.md
```
- <define current step>
- <define next step>
```


2.md
```
- <define current step>
- <define next step>
```

...

After testing the above approach, it doesn't work well. Note that when the number and complexity of substeps or subskills reaches a certain level, it doesn't work as expected and always terminates prematurely.
-------------


I have two other ideas:


## Idea 1:

Skills can call scripts, so wrap the md prompts in a script

SKILL.md:
```
---
skills header
---

1.sh : <conditions to call this script, supports parameters>
2.sh : <conditions to call this script, supports parameters>
3.sh : <conditions to call this script, supports parameters>
...
```

Each script should contain at least this content, for example

1.sh

```
# Previous step state
# Current subtask definition
# Under what conditions call the next script
#
```

In this approach, the script supports parameters and output. Parameters can be state information or summary information from the previous step, and the output content can be read by the Agent (claudecode) as the prompt for the current step, including the prompt to drive the next step.

This prompt defines
- Current task definition, driving the Agent (claudecode) to execute the current subtask
- Under what conditions call the next script, to trigger task execution recursion (decision graph)

## Idea 2:

Replace the script content from Idea 1 with (starting a new Claude process)

```
$ cat "prompt" | claude
```

The prompt contains

- Previous step state
- Current subtask definition
- Under what conditions call the next claude process

-----

I prefer Idea 1. If Idea 1 doesn't work well, then try Idea 2.

Please help me
- Evaluate the feasibility of these ideas
- Whether you have better implementation approaches


