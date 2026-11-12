# Kiro Project Blueprint: Programming Language Tutor Chatbot (Python, Java, C)

**Project root:** `C:\Python_Programming_Tutor`

**Purpose of this document:** Give Kiro a complete project blueprint for
analyzing and implementing the approved capstone. The original proposal
was approved as a Python Programming Tutor Chatbot. The approved
project's scope is now being expanded to support **Python, Java, and
C**. Preserve the original educational purpose and approved design; do
not turn it into a different project.

**Instruction to Kiro:** First inspect the actual repository and report
what exists, what is missing, and any conflicts with this document. Do
not overwrite files, delete data, train a model, or implement the whole
system immediately. Back up affected files and work incrementally. Do
not claim a test, audit, or training run passed unless it was actually
executed.

------------------------------------------------------------------------

## 1. Approved proposal alignment

### Updated title

**A Programming Language Tutor Chatbot for Python, Java, and C**

If the professor wants the original title preserved, retain *Python
Programming Tutor Chatbot* and document Java and C as an approved scope
expansion. Do not claim the title itself was re-approved unless that
happened.

### Domain

**Computer Science Education --- Programming Language Learning
Assistance.**

The audience is complete beginners and students with some programming
experience. AI and machine learning are implementation technologies, not
the main domain.

### Project description

A web-based educational chatbot that helps learners understand concepts
and syntax in Python, Java, and C. It classifies user requests using a
group-built and group-trained AI model, retrieves explanations from an
original knowledge base, presents curated examples, generates limited
code from validated templates, explains code, provides bounded debugging
guidance, predicts output for a supported subset, compares concepts, and
provides quizzes. It uses language detection, context management, and
task routing to answer one or multiple requests in a message.

### Objectives

1.  Build a web tutor for Python, Java, and C.
2.  Create an original labeled question dataset.
3.  Implement and train an Artificial Neural Network (ANN) for intent
    classification using supervised learning.
4.  Evaluate the model with held-out data and documented metrics.
5.  Build an original language-aware knowledge base, code-example
    library, template library, and quiz bank.
6.  Support explanations, syntax, examples, controlled code generation,
    code explanation, debugging guidance, output prediction,
    comparisons, quizzes, and follow-ups.
7.  Handle multiple intents and language selection in a single user
    message.
8.  Store conversation history locally and provide a clear-history
    control.
9.  Test correctness, safety, integration, and performance.
10. Deploy a live web application that does not depend on online AI
    services.

### Scope and limitations

**In scope:** Python, Java, and C fundamentals; variables and types;
operators; conditions; loops; functions/methods; arrays and collections;
strings; classes and objects where appropriate; modules/packages/header
files; input/output; common errors; quizzes; contextual follow-ups;
Flask web UI; SQLite history; local model inference.

**Limitations:** This is an educational assistant, not a compiler or a
full IDE. Responses are bounded by the dataset, rules, knowledge base,
and templates. It must not execute arbitrary user-submitted or generated
code. The classifier can make mistakes on ambiguous or unsupported
messages. Every code block must be clearly labeled with its programming
language. The system must not use a third-party chatbot API or a
downloaded pretrained chatbot model.

### Expected outcomes

-   Functional web application for Python, Java, and C.
-   Original dataset and documented taxonomy.
-   Self-trained ANN and evaluation report.
-   Original knowledge base, code examples, validated templates, and
    quizzes.
-   Multi-intent routing and conversation context.
-   Conversation history and clear-history controls.
-   Unit, integration, end-to-end, and safety tests.
-   Deployment guide and live demonstration.

The earlier target of accuracy and macro F1 of 0.85 can remain as a
**goal**, not a guaranteed outcome. Report per-intent metrics and
language-specific results so one strong language does not hide a weak
one.

------------------------------------------------------------------------

## 2. SDLC model: resolve this requirement carefully

The approved proposal previously selected the **Iterative and
Incremental Model**. However, the teacher's supplied list contains
**Waterfall, Spiral, V-Model, RAD, and Agile**, and does not explicitly
list Iterative and Incremental as a separate choice.

Do not silently rewrite the approved proposal. Ask the professor whether
the approved Iterative and Incremental approach is acceptable. If the
professor requires one model strictly from the list, **Agile is the
closest fit**, because Agile commonly uses short iterations and
incremental delivery. In that case, the wording could be "Agile Model
using iterative and incremental development cycles," but obtain
confirmation before changing the approved proposal.

Suggested increments: 1. Requirements, intent taxonomy, and dataset
schema. 2. Dataset audit, ANN training, and evaluation. 3. Python
knowledge and templates. 4. Java knowledge and templates. 5. C knowledge
and templates. 6. Multi-intent planning, language detection, and context
handling. 7. Flask integration, UI, and SQLite history. 8. End-to-end
testing, corrections, and deployment.

Testing occurs throughout development; the increments can overlap.

------------------------------------------------------------------------

## 3. Build-from-scratch AI rule

The teacher requires the group to design, code, and train/build its own
AI component.

**Not allowed:** online AI/chatbot APIs or hosted inference
(OpenAI/ChatGPT, Gemini, Claude, Dialogflow, Watson, hosted Hugging Face
inference, or similar); plugging in a pretrained chatbot/language model
as the brain; relying on a paid online AI service to generate answers.

**Allowed:** Python, scikit-learn, NumPy, standard libraries, a
self-created dataset and knowledge base, original rules/templates, a
plain web interface, and a model trained locally by the group. Hosting
the group's own Flask application is acceptable if inference does not
rely on an external AI service.

Record dataset versions, training settings, library versions, commands,
metrics, and model artifacts.

------------------------------------------------------------------------

## 4. AI model, learning type, and libraries

### Recommended required AI

Use a **feed-forward Artificial Neural Network (ANN)** for text intent
classification. A practical initial implementation is scikit-learn's
`MLPClassifier`, with text transformed into features by
`TfidfVectorizer`.

**Learning type: supervised learning.** Each training message has
human-labeled intent(s). This is not unsupervised or semi-supervised
learning.

Pipeline: 1. Normalize user text. 2. Convert text into numerical
features with `TfidfVectorizer`. 3. Pass features to the group's trained
`MLPClassifier`. 4. Obtain intent scores/predictions. 5. Apply
confidence thresholds and routing rules. 6. Detect language and resolve
topic/context. 7. Route to knowledge retrieval, a validated template,
quiz handler, or another deterministic service. 8. Format a response.

The ANN classifies the request; it does not itself store facts or
generate unrestricted code. The full chatbot combines the ANN with
original content, rules, context handling, and template-based code
generation.

### Keep earlier model comparison if feasible

The earlier plan proposed comparing TF-IDF + Logistic Regression and
TF-IDF + Linear SVM. These can be optional baseline models, but they are
**not neural networks**. To demonstrate the required ANN, implement and
evaluate the ANN regardless of which model scores best.

Compare: - TF-IDF + Logistic Regression (baseline). - TF-IDF + Linear
SVM (baseline). - TF-IDF + `MLPClassifier` (required ANN).

Measure accuracy, macro F1, per-intent precision/recall/F1, confusion
matrix, training time, and multi-label performance where applicable. Use
validation data for tuning and reserve the test set for final
evaluation. If a baseline outperforms the ANN, document the result and
consult the professor before making the ANN non-production.

### PyTorch or Keras?

They are not required for the initial plan. scikit-learn's
`MLPClassifier` is a genuine feed-forward neural network and is easier
to train and integrate. Use PyTorch or TensorFlow/Keras only if the
instructor requires it or the project demonstrates a need for a custom
architecture.

### Training time versus YOLOv8

This text classifier is generally far lighter than computer-vision
training. A TF-IDF + small MLP on a few thousand or tens of thousands of
text examples will commonly train on CPU in seconds to minutes,
depending on data size, feature dimensions, hardware, and settings. A
24-hour training run should not normally be necessary. Measure actual
runtime; do not promise a fixed time.

------------------------------------------------------------------------

## 5. Component responsibilities

  -----------------------------------------------------------------------
  Component                           Responsibility
  ----------------------------------- -----------------------------------
  ANN intent classifier               Predict what task the user requests

  Language detector                   Identify Python, Java, C, multiple
                                      languages, or unspecified

  Topic resolver                      Map aliases and phrasing to
                                      canonical topics

  Context manager                     Resolve "why?", "another example,"
                                      "do the same in C"

  Multi-intent planner                Break a message into ordered tasks
                                      and dependencies

  Knowledge retriever                 Retrieve reviewed explanations

  Code-template engine                Fill validated, language-specific
                                      templates

  Code analyzer                       Inspect supported snippets as text
                                      without executing them

  Output predictor                    Predict only a limited, supported
                                      subset with deterministic logic

  Quiz handler                        Retrieve/assemble questions from
                                      the original quiz bank

  Response formatter                  Present sections and labeled code
                                      blocks

  Conversation store                  Persist history/context metadata in
                                      SQLite
  -----------------------------------------------------------------------

The model must not be responsible for every behavior. The system should
be explainable and testable.

------------------------------------------------------------------------

## 6. Intent taxonomy

Retain the original 13 intents as the initial taxonomy. Do not create
separate intent labels just because the language differs; represent
language separately.

1.  `greeting`
2.  `bot_capabilities`
3.  `explain_concept`
4.  `show_syntax`
5.  `show_example`
6.  `generate_code`
7.  `explain_code`
8.  `debug_code`
9.  `predict_output`
10. `compare_concepts`
11. `request_quiz`
12. `follow_up`
13. `clarification`

Definitions: - `greeting`: social opening. - `bot_capabilities`: asks
what the bot can teach/do. - `explain_concept`: asks for a concept
definition or explanation. - `show_syntax`: requests syntax/form. -
`show_example`: requests an example. - `generate_code`: asks for code to
achieve a goal. - `explain_code`: asks to explain supplied or retrieved
code. - `debug_code`: asks for error diagnosis/correction. -
`predict_output`: asks what supported code would print/return. -
`compare_concepts`: asks for similarities/differences between concepts
or languages. - `request_quiz`: asks for practice questions. -
`follow_up`: contextual continuation. - `clarification`: clarifies or
narrows a request.

A message may have multiple labels. Example: "Write a Java program to
add two numbers and explain every line" has `generate_code` and
`explain_code`, with `generate_code` as the primary intent. For
multi-label training, use multi-hot targets or an appropriate
multi-label approach; do not claim a single-label classifier learns
simultaneous intents.

Do not label every follow-up only as `follow_up` if a concrete task is
also present. "Show another Java loop example" can be `follow_up` +
`show_example`.

------------------------------------------------------------------------

## 7. Language and topic detection

### Language labels

Use a separate field or component with these values: - `python` -
`java` - `c` - `multiple` - `unspecified`

Use explicit names/aliases, reliable language-specific cues, and
conversation context. Do not infer C from the single letter "C" in an
unrelated sentence. Do not infer Java from `class` alone because Python
also has classes. Ask for clarification when the language materially
changes the answer and cannot be inferred confidently.

For a language-unspecified question: - carry forward the active language
for a clear follow-up; - answer language-independent questions generally
if appropriate; - otherwise ask which language the user wants.

### Shared topic tags

`programming_basics`, `variables`, `data_types`, `operators`,
`conditions`, `loops`, `functions`, `input_output`,
`arrays_collections`, `strings`, `errors_debugging`,
`object_oriented_programming`, `modules_libraries`, `scope`,
`recursion`.

### Python-specific topic tags

`python_indentation`, `python_list`, `python_tuple`, `python_set`,
`python_dictionary`, `python_def`, `python_import`, `python_main_guard`,
`python_self`, `python_init`.

### Java-specific topic tags

`java_class`, `java_main_method`, `java_types`, `java_methods`,
`java_constructors`, `java_access_modifiers`, `java_inheritance`,
`java_interfaces`, `java_packages`, `java_import`, `java_arrays`,
`java_collections`, `java_exceptions`.

### C-specific topic tags

`c_header_files`, `c_main_function`, `c_variables_types`,
`c_format_specifiers`, `c_operators`, `c_conditions`, `c_loops`,
`c_functions`, `c_arrays`, `c_strings`, `c_pointers`, `c_structs`,
`c_preprocessor`, `c_memory_basics`, `c_errors`.

Keep tags canonical and documented. Every code example/template must
specify its language.

------------------------------------------------------------------------

## 8. Dataset plan and minimum counts

The latest stated requirement is **at least 150 examples per intent**.
The earlier Python-only plan targeted 300 per intent. Use 150 as the
minimum and aim for 300 where feasible without sacrificing quality.

There are 13 intents, so 13 × 150 = **1,950 intent-example assignments**
as a planning benchmark. This does not necessarily mean 1,950 unique
rows because genuinely multi-intent rows may count toward more than one
intent. Never add irrelevant labels just to inflate counts. Report
unique rows and valid examples per intent separately.

Cover all three languages. Language-specific intents should have
balanced examples across Python, Java, and C. General
greetings/capability questions do not need mechanical triplication, but
include natural questions about all supported languages.

### Quality requirements

Include beginner and intermediate phrasing, short and detailed requests,
common variations, language-explicit questions, context-dependent
follow-ups, multiple-intent messages, ambiguous questions that require
clarification, and out-of-scope examples. Avoid 150 near-identical
paraphrases.

### Existing CSV header

The existing Python dataset schema is:

``` csv
text,intents,primary_intent,topic_tags,source_group,context_required,review_status
```

Preserve existing data and schema unless a migration is planned. A
clearer three-language schema adds an explicit `language_tags` column:

``` csv
text,intents,primary_intent,topic_tags,language_tags,source_group,context_required,review_status
```

If changing schema, first make a dated backup, document the migration,
and update all readers and validators. `intents`, `topic_tags`, and
`language_tags` should be valid JSON-array strings stored in CSV fields.
Validate the file with a CSV parser.

### Sample rows

These are schema examples, not the completed dataset:

``` csv
text,intents,primary_intent,topic_tags,language_tags,source_group,context_required,review_status
"How do variables work in Python?","[""explain_concept""]","explain_concept","[""variables""]","[""python""]","variables_explain_01",false,"accepted"
"Show Java syntax for a for loop.","[""show_syntax""]","show_syntax","[""loops"",""java_loops""]","[""java""]","java_for_syntax_01",false,"accepted"
"Write a C program that adds two integers, then explain it.","[""generate_code"",""explain_code""]","generate_code","[""input_output"",""c_functions"",""c_variables_types""]","[""c""]","c_add_two_ints_01",false,"accepted"
"Compare Python lists with Java arrays.","[""compare_concepts""]","compare_concepts","[""arrays_collections"",""python_list"",""java_arrays""]","[""python"",""java""]","python_list_java_array_compare_01",false,"accepted"
"Can you show another example?","[""follow_up"",""show_example""]","show_example","[""programming_basics""]","[]","context_followup_example_01",true,"accepted"
"Can you teach me Java or C?","[""clarification""]","clarification","[""programming_basics""]","[""java"",""c""]","language_choice_01",false,"accepted"
```

`source_group` must group related paraphrases/near-duplicates so they
stay in the same data split. Recommended split is group-aware 70% train,
15% validation, 15% test where feasible. Do not fit TF-IDF on the whole
dataset before splitting. Do not tune against the test set.

### Dataset audit before training

Validate: - required columns, non-empty text, correct CSV parsing; -
JSON-array fields parse; - all intents/topic/language tags are
approved; - `primary_intent` appears in `intents`; - `context_required`
is a valid boolean; - `review_status` is allowed; - duplicates and near
duplicates are flagged; - per-intent counts meet the minimum; -
per-language coverage is reported; - source groups do not leak across
splits; - each split is usable; - multi-intent labels are genuinely
appropriate.

Do not claim full validation until these checks run against the
consolidated saved CSV.

------------------------------------------------------------------------

## 9. Knowledge base

The dataset teaches the classifier to recognize intent; the knowledge
base supplies the actual educational content. Keep these separate.

Suggested record:

``` json
{
  "id": "python_for_loop_intro",
  "language": "python",
  "topic": "loops",
  "title": "Python for loop",
  "level": "beginner",
  "aliases": ["for loop", "iterate over a sequence"],
  "definition": "A for loop repeats a block for each item in an iterable.",
  "syntax_example_id": "python_for_syntax_01",
  "example_ids": ["python_for_example_01"],
  "common_mistakes": ["Incorrect indentation"],
  "related_topics": ["range", "while_loops"],
  "source_name": "Python documentation",
  "source_url": "https://docs.python.org/3/tutorial/controlflow.html"
}
```

Suggested files: - `data/knowledge_base.json` --- concepts and
explanations. - `data/code_examples.json` --- curated reviewed
examples. - `data/code_templates.json` --- constrained code-generation
templates. - `data/quizzes.json` --- questions, answers, explanations,
language and topic. - `data/intent_dataset.csv` --- training examples. -
`data/evaluation_cases.csv` --- held-out, hand-reviewed end-to-end
cases. - `models/` --- model/pipeline artifacts and metadata. -
`results/` --- metrics, data audits, confusion matrices and reports.

Use primary references and record sources: - Python:
https://docs.python.org/3/ - Java: https://docs.oracle.com/en/java/ - C:
choose a reputable C language reference and document it. - W3Schools can
be supplementary for beginner explanations where relevant.

Write original explanations; do not copy large passages verbatim. Use
stable IDs to connect concepts, examples, and templates.

------------------------------------------------------------------------

## 10. Code generation and basic program coverage

Do not call an external LLM. Use curated examples and validated,
language-specific templates.

Prioritize templates for: - hello world/output; - variables and basic
types; - input/output; - addition and simple calculator; - if/else; -
for/while/nested loops; - functions/methods; - arrays/lists and
iteration; - strings; - simple classes/objects where appropriate; -
imports/modules/packages/header files; - basic exception/error
handling; - average calculator, grade calculator, and menu-driven
calculator.

Do not translate a Python template by merely changing keywords. Java
requires class/program structure; C typically needs headers and a `main`
function; Python uses its own indentation and function conventions.

Example: Python loop

``` python
for number in range(1, 6):
    print(number)
```

Example: Java loop

``` java
public class Main {
    public static void main(String[] args) {
        for (int number = 1; number <= 5; number++) {
            System.out.println(number);
        }
    }
}
```

Example: C loop

``` c
#include <stdio.h>

int main(void) {
    for (int number = 1; number <= 5; number++) {
        printf("%d\n", number);
    }
    return 0;
}
```

Suggested generation flow: 1. Classify the request and detect language.
2. Extract supported parameters. 3. Select an approved template. 4. Fill
only validated placeholders. 5. Apply structural and safety checks to
the text. 6. Return code and explanation. 7. Ask for clarification or
state the limitation if unsupported.

Never execute generated or user-submitted code. Do not use Python
`eval()` or `exec()` on user input. Do not compile or run arbitrary C,
Java, or Python source on the server.

------------------------------------------------------------------------

## 11. Multiple-intent analysis and response logic

Example request: **"Write a Java program that adds two numbers and
explain every line."**

Labels: `generate_code`, `explain_code`. Primary: `generate_code`.
Language: `java`.

Task plan: 1. Retrieve a validated Java addition template. 2. Fill
approved parameters. 3. Explain the resulting code line by line. 4.
Return both code and explanation.

Example: **"Compare Python lists and Java arrays, then quiz me."**

Labels: `compare_concepts`, `request_quiz`. 1. Retrieve a supported
comparison. 2. Present it. 3. Retrieve or assemble a quiz for the topic.

Use ANN multi-label prediction, primary-intent selection, language/topic
detection, dependency rules, ordered task execution, and response
composition. The classifier alone should not decide task order. A
request to generate code and then explain it has a dependency: the
explanation must match the code actually generated.

### Confidence and fallback

-   Low or conflicting intent confidence: ask a concise clarification.
-   Ambiguous language that changes the answer: ask which language.
-   Clear task plus unclear secondary task: complete the clear part if
    useful and safe, then clarify the rest.
-   Keep active topic/language for "why?", "another example," "make it
    simpler."
-   Let users explicitly switch language at any time.
-   Do not treat each follow-up as unrelated.

------------------------------------------------------------------------

## 12. Conversation context

Store only useful context: - session/conversation ID; - user message and
assistant response; - timestamp; - active language and topic; - last
generated template/example ID; - pending clarification; - detected
intent labels/scores where useful.

The ANN classifies the current message. Deterministic context rules
resolve references and carry forward the language/topic. Do not rely
only on feeding the entire conversation history into the classifier.

Provide clear-history functionality and avoid unnecessary personal data
collection.

------------------------------------------------------------------------

## 13. Debugging and output prediction

### Debugging

The chatbot may explain supplied error messages, recognize supported
common mistakes, and suggest corrections when a known pattern/template
matches. Distinguish confirmed syntax issues from possible logic issues.
Do not claim code was executed.

### Code explanation

Use known templates or a bounded parser/rule set. If a snippet is
unsupported, state the limitation or request a smaller snippet.

### Output prediction

Support only a documented subset of safe constructs. Use a deterministic
parser/interpreter implemented by the group for that subset. Never
execute the source code. If unsupported, say the chatbot cannot reliably
predict it rather than guessing.

------------------------------------------------------------------------

## 14. Technology stack and live deployment

Recommended: - Backend: Python + Flask. - Frontend: HTML, CSS,
JavaScript. - AI: scikit-learn `TfidfVectorizer` + trained
`MLPClassifier`. - Optional comparisons: Logistic Regression and Linear
SVM. - Training data: CSV. - Knowledge/examples/templates/quizzes:
JSON. - History: SQLite. - Model persistence: joblib, with version
metadata. - Tests: pytest plus browser/manual end-to-end tests. -
Deployment: Python-compatible hosting for the Flask app.

### PHP or Python?

PHP can call a Python model through an API, but it creates a second
backend and more integration work. Flask can handle intent
classification, language detection, task planning, knowledge retrieval,
templates, and context in one Python application. **Recommendation: keep
the web backend in Python/Flask.** A JavaScript frontend can call Flask
HTTP endpoints. Train the model offline and load it at app startup; do
not retrain per request.

### Suggested structure

Preserve the actual repository layout when possible. Inspect before
creating or renaming files.

``` text
C:\Python_Programming_Tutor\
├── app\
│   ├── routes\
│   ├── services\
│   ├── classifier\
│   ├── knowledge\
│   ├── conversation\
│   ├── validators\
│   ├── templates\
│   └── static\
├── data\
│   ├── intent_dataset.csv
│   ├── knowledge_base.json
│   ├── code_examples.json
│   ├── code_templates.json
│   ├── quizzes.json
│   └── evaluation_cases.csv
├── models\
├── results\
├── scripts\
├── tests\
├── backups\
├── requirements.txt
└── README.md
```

Create missing folders only after inspecting the actual project. Keep
training/evaluation scripts separate from production request handlers.

------------------------------------------------------------------------

## 15. Training and evaluation workflow

1.  Audit the consolidated dataset.
2.  Back up the reviewed dataset with a dated version.
3.  Make group-aware train/validation/test splits.
4.  Fit TF-IDF on training data only.
5.  Train baseline models if included.
6.  Train the required ANN with recorded settings and random seed.
7.  Tune using validation data only.
8.  Evaluate on the held-out test set.
9.  Report accuracy, macro F1, per-intent precision/recall/F1, confusion
    matrix, multi-label metrics, training time, and language-level
    performance.
10. Test the full chatbot pipeline separately: correct intent does not
    guarantee correct content/code.
11. Save versioned model artifacts and metadata that match the
    taxonomy/data.
12. Load the tested model at app startup.
13. Add newly reviewed examples through a deliberate dataset version and
    retraining process.

Keep `evaluation_cases.csv` separate from classifier training. It is for
hand-reviewed end-to-end chatbot tests.

------------------------------------------------------------------------

## 16. Tests before the demonstration

### Dataset

-   CSV parses; required columns exist.
-   JSON arrays and labels are valid.
-   Minimum counts and language coverage are reported.
-   Duplicates/near duplicates are flagged.
-   No source-group leakage across splits.
-   Multi-intent labels are valid.

### Model

-   Training completes reproducibly.
-   Saved pipeline loads.
-   Predictions use approved labels.
-   Low-confidence input triggers fallback.
-   Per-intent and per-language metrics are reported.

### Functional

-   Explanations, syntax, examples and quizzes work in all languages.
-   Language selection works.
-   Generated code uses the correct language template.
-   Multi-intent tasks execute in order.
-   Follow-ups preserve context.
-   Language changes are honored.
-   Unsupported debugging/output requests are handled honestly.

### Safety

-   User/generated code is never executed.
-   Malformed input does not crash the app.
-   HTML output is escaped.
-   No external AI API is called.
-   Unsupported requests trigger clarification or a clear limitation.

### End-to-end examples

1.  "Explain variables in Python."
2.  "Show Java syntax for a method."
3.  "Write a C loop that prints 1 to 5."
4.  "Write a Java addition program and explain every line."
5.  "Compare Python lists with C arrays."
6.  "Show another example" after a topic has been discussed.
7.  "Do the same in C" after a Python example.
8.  "Predict the output" for a supported loop.
9.  "What can you teach me?"
10. Unsupported code that should not be executed.

------------------------------------------------------------------------

## 17. Group roles

The teacher requires clear roles for a group of 6--7. Assign actual
member names later; do not invent names.

-   **Project Manager:** schedule, task assignment, coordination.
-   **Lead Developer/System Architect:** architecture, integration, code
    review.
-   **AI/ML Developer:** dataset pipeline, ANN training, evaluation,
    persistence.
-   **Dataset/Knowledge Lead:** intent examples, language balance,
    references, content, templates, quizzes.
-   **Backend Developer:** Flask routes, orchestration, context,
    storage.
-   **Frontend Developer:** UI, code formatting, language selection,
    history controls.
-   **QA/Tester and Documentation Lead:** tests, regression, reports,
    user guide.

For six members, combine roles as practical and record the allocation in
the Project Management Plan.

------------------------------------------------------------------------

## 18. Instructions for Kiro: staged work only

### Phase A --- Analyze without modifying

For this initial audit, check whether the current Kiro environment can access official documentation websites. Do not assume internet access is available. If browsing is unavailable, report it and list the claims that still need verification. Do not modify or overwrite project files during the initial audit; present findings and wait for approval before making repository changes.

1.  Inspect actual files and repository structure.
2.  Read any existing proposal/project documents.
3.  Audit the existing dataset state and schema.
4.  Compare repository contents with this blueprint.
5.  Report conflicts, gaps, risks, and a prioritized plan.

### Phase B --- Design and request review

6.  Finalize the intent taxonomy and language/topic taxonomy.
7.  Propose the dataset schema and any migration.
8.  Design the ANN and evaluation process.
9.  Design multi-intent routing, language detection, context, and
    fallbacks.
10. Define JSON schemas for knowledge, examples, templates, and quizzes.
11. Present designs before generating large datasets or changing
    existing files.

### Phase C --- Implement incrementally

12. Back up files before edits.
13. Implement one logical component at a time.
14. Add tests with each component.
15. Run tests and report actual results.
16. Do not claim tests passed unless run.
17. Do not claim the dataset is complete until counts and audits pass.
18. Do not train until the consolidated dataset and splits are approved.
19. Do not replace architecture or user data without approval.

### Phase D --- Integrate and deploy

20. Integrate the trained model with Flask.
21. Test each language independently and together.
22. Test multi-intent requests and contextual follow-ups.
23. Run safety and end-to-end tests.
24. Document hosting requirements and deployment.
25. Deploy after approval and after required hosting
    credentials/configuration are available.

------------------------------------------------------------------------

## 19. Final decision summary

  -----------------------------------------------------------------------
  Question                            Decision
  ----------------------------------- -----------------------------------
  Domain                              Computer Science Education ---
                                      Programming Language Learning
                                      Assistance

  Languages                           Python, Java, C

  Required AI component               Self-trained ANN

  Learning type                       Supervised learning

  Initial model                       TF-IDF + scikit-learn
                                      `MLPClassifier`

  Baselines                           Logistic Regression and Linear SVM,
                                      if retained

  Backend                             Python + Flask

  Frontend                            HTML/CSS/JavaScript

  Data                                CSV training dataset; JSON learning
                                      content; SQLite history

  Code generation                     Validated language-specific
                                      templates

  Multiple intents                    ANN multi-label classification +
                                      deterministic task planner

  Language detection                  Explicit cues, aliases, context,
                                      clarification

  Dataset minimum                     150 examples per intent; aim higher
                                      where feasible

  Split                               Group-aware train/validation/test

  SDLC                                Approved proposal says Iterative
                                      and Incremental; confirm with
                                      professor because supplied list
                                      names Agile instead

  Live deployment                     Host Flask with self-trained model;
                                      no online AI service

  Training cost                       Expected much lighter than YOLOv8;
                                      measure actual time

  Code execution                      Never execute arbitrary user or
                                      generated code
  -----------------------------------------------------------------------

**Core principle:** The ANN classifies intent. The language detector
selects Python, Java, or C. The context manager resolves follow-ups. The
task planner orders multiple actions. The knowledge base supplies
reviewed explanations. The template engine produces constrained code.
Validators and tests protect reliability. Flask serves the web
application.

This design is explainable, testable, compatible with the
build-from-scratch requirement, and achievable for a student capstone.

## Language History and Basic Information Requirements

Kiro must inspect the existing repository and curriculum files before making changes. Expand the learning content to cover the history and basic characteristics of Python, Java, and C. The facts below are starting points to verify, not a substitute for checking authoritative sources.

### Required coverage for each language

For Python, Java, and C, include:
- Creator(s), organization or place of origin, and approximate development period.
- First public release or initial publication year, where reliably documented.
- Original motivation and the problems the language was designed to address.
- Important milestones and major evolution/version changes at a beginner-friendly level.
- Main purpose, programming paradigms, and how programs are typically executed or compiled.
- Core characteristics, strengths, limitations, and common application areas.
- Typical development tools and runtime/compiler environment, explained at an introductory level.
- Beginner-friendly terminology and links to related concepts taught by the chatbot.
- A concise beginner-friendly answer and a more detailed explanation when appropriate.

### Historical starting points to verify

- **Python:** Guido van Rossum began developing Python in the late 1980s; its first public release was in 1991. Explain its emphasis on readable syntax and its evolution, including the Python 2-to-3 transition.
- **Java:** Java was developed at Sun Microsystems by James Gosling and the team working on the language, originally called Oak; it was publicly released in 1995. Explain the role of the Java Virtual Machine (JVM) and the goal of portability.
- **C:** C was developed by Dennis Ritchie at Bell Labs in the early 1970s, in the context of Unix and systems programming. Explain its influence, compilation model, and low-level memory capabilities.

Verify historical claims and dates before marking knowledge records approved. If authoritative sources disagree or a date is uncertain, state the uncertainty rather than presenting a guess as fact.

### Source policy

Prefer primary and official sources:
- Python documentation: https://docs.python.org/3/
- Oracle Java documentation: https://docs.oracle.com/en/java/
- C language reference: https://en.cppreference.com/w/c
- Supplementary beginner explanations: https://www.w3schools.com/

Kiro may browse these websites if its configured environment has internet access and the necessary permissions. If access is unavailable, report that limitation and use only sources already available in the repository. Never claim to have verified a website that was not accessed. Record the source name and exact URL in relevant knowledge-base records. Do not invent citations, URLs, source dates, or verification results.

### Knowledge-base record requirements

Use the existing knowledge-base format where possible. Each history/fundamentals record should contain:
- Stable record ID.
- Language (`python`, `java`, `c`, or an explicitly shared language tag).
- Topic and title.
- Intended learner level.
- Search aliases and common beginner phrasings.
- Short definition or direct answer.
- Expanded explanation and key points.
- Related topics and relevant example IDs.
- Source name and exact source URL.
- Review status indicating whether the record is verified and approved.

Keep historical facts separate from language-specific syntax lessons. Audit and extend existing records instead of duplicating them unnecessarily. Preserve the approved dataset, intent taxonomy, file organization, and other project decisions unless the user explicitly approves a change.

### Curriculum audit checklist

For each language, check coverage of:
1. Creator, origin, development period, and first public release.
2. Original design motivation and historical evolution.
3. Purpose, paradigms, execution/compilation model, and core characteristics.
4. Strengths, limitations, and common uses.
5. Beginner terminology, syntax fundamentals, and language-specific concepts.
6. Links between history/basic information and existing intent, topic, knowledge-base, and evaluation structures.

Report missing, incomplete, duplicated, or unsupported content separately. Distinguish verified facts from proposed content and assumptions. Do not silently mark unverified information as complete.
