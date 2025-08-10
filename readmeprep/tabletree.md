## 📂 Project Structure (Tree View)

```markdown
- .circleci                     
  - code-config.yml               
  - config.yml                      #  setup: true (setup pipeline) 
  - custom-circleci-cli-script.sh   #  custom script to build list / generate final config 
  - docs-config.yml               
  - no-updates.yml                
  - shared                          #  directory to pack (.circleci/shared-config.yml) 
    - @paramters.yml                
    - @shared.yml                   
    - jobs                          
      - any-change.yml                
      - lint.yml                      
      - test.yml                      
    - workflows                     
      - run-on-any-change.yml         
- comments.json                 
- docs                          
  - my-docs.txt                   
- print-tree.py                 
- src                           
  - my-code.txt                   
```

## 📊 Project Structure (Table View)

| Path | Type | Comment |
|------|------|---------|
| `.circleci` | Folder |  |
| `.circleci/code-config.yml` | File |  |
| `.circleci/config.yml` | File |  setup: true (setup pipeline) |
| `.circleci/custom-circleci-cli-script.sh` | File |  custom script to build list / generate final config |
| `.circleci/docs-config.yml` | File |  |
| `.circleci/no-updates.yml` | File |  |
| `.circleci/shared` | Folder |  directory to pack (.circleci/shared-config.yml) |
| `.circleci/shared/@paramters.yml` | File |  |
| `.circleci/shared/@shared.yml` | File |  |
| `.circleci/shared/jobs` | Folder |  |
| `.circleci/shared/jobs/any-change.yml` | File |  |
| `.circleci/shared/jobs/lint.yml` | File |  |
| `.circleci/shared/jobs/test.yml` | File |  |
| `.circleci/shared/workflows` | Folder |  |
| `.circleci/shared/workflows/run-on-any-change.yml` | File |  |
| `comments.json` | File |  |
| `docs` | Folder |  |
| `docs/my-docs.txt` | File |  |
| `print-tree.py` | File |  |
| `src` | Folder |  |
| `src/my-code.txt` | File |  |
