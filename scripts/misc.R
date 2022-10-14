### This is mostly code that was just run once and is being documented. Yao had
### a master sheet called `conditions.tbl` that is being broken down here into
### separate control files.
library(stringr)
library(readr)
library(dplyr)

condition_levels = c("coloc", "noinj", "cr", "4ap", "bapta", "pr", "br", "am")

conditions = (
    read_table2("inputs/conditions.tbl")
    %>% mutate(condition=factor(cellcond, labels=condition_levels), cell=str_sub(cell, end=8))
)

## for colocalization, we use the table of biocytin-filled neurons, because
## there is some overlap with other categories

## for plasticity:
plasticity_epochs = filter(conditions, condition %in% c("cr", "noinj", "bapta", "pr")) %>%
    select(cell, epoch, condition)
write_csv(plasticity_epochs, "plasticity_epochs.csv")

## for 4-AP reversal
epoch_levels = c("mid", "first", "pre", "post")
reversal_epochs = (
    filter(conditions, condition=="4ap")
    %>% mutate(epoch_type=factor(epochcond, labels=epoch_levels))
    %>% select(cell, epoch, condition, epoch_type)
)
write_csv(reversal_epochs, "reversal_epochs.csv")


