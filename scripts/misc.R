### This is mostly code that was just run once and is being documented. Yao had
### a master sheet called `conditions.tbl` that is being broken down here into
### separate control files.
library(stringr)
library(readr)
library(dplyr)

condition_levels = c("coloc", "noinj", "cr", "4ap", "bapta", "pr", "br", "am")
epoch_levels = c(

conditions = read_table("inputs/conditions.tbl") %>%
    mutate(condition=factor(cellcond, labels=condition_levels))

## for colocalization, we use the table of biocytin-filled neurons, because
## there is some overlap with other categoris

## for plasticity:
plasticity_epochs = filter(conditions, condition %in% c("cr", "noinj", "bapta", "pr")) %>%
    select(cell, epoch, condition)

write_csv(plasticity_epochs, "plasticity_epochs.csv")
