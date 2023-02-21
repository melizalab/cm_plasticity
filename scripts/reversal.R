### quantify reversal of plasticity with potassium channel blockers
library(readr)
library(stringr)
library(tidyr)
library(dplyr)
library(ggplot2)
library(lmerTest)
library(emmeans)

## can use egg::theme_article() to get a full axis frame
my.theme <- theme_classic() + theme(legend.position="none",
                                    axis.line=element_line(linewidth=0.25),
				    axis.ticks=element_line(linewidth=0.25),
				    axis.title=element_text(size=6),
                                    axis.text=element_text(size=5),
				    strip.placement="outside",
				    strip.text=element_text(size=6),
				    strip.background=element_blank())
update_geom_defaults("point", list(fill="white", shape=21, size=1.1))
update_geom_defaults("line", list(linewidth=0.25))

## epoch types are tagged in the control file
## select first, last (pre), and post epochs for each cell. Only use last (good) post epoch
## There are no narrow-spiking cells, but we only look at initially tonic neurons
reversal_epochs = (
    read_csv("inputs/reversal_epochs.csv")
    %>% group_by(cell, epoch_cond)
    %>% filter(row_number()==n())
    ## drop dtx for now
    %>% filter(condition=="4ap")
)
cell_info = (
    read_csv("build/cell_info.csv")
    %>% mutate(bird=str_sub(bird, end=8), sire=str_sub(sire, end=8), dam=str_sub(dam, end=8))
)
epoch_stats = (
    read_csv("build/epoch_stats.csv")
    %>% inner_join(reversal_epochs, by=c("cell", "epoch"))
    %>% filter(epoch_cond %in% c("first", "pre", "post"))
    %>% mutate(epoch_cond=factor(epoch_cond, levels=c("first", "pre", "post")))
    %>% group_by(cell)
    %>% filter(first(duration_mean) > 1.0, spike_width > 0.9)
    %>% inner_join(cell_info, by="cell")
)

## check for bad epochs
select(epoch_stats, cell, epoch, epoch_cond, Vm, delta_Rs, delta_Rm) %>% group_by(cell) %>% filter(any(abs(delta_Rs) > 0.3))
select(epoch_stats, cell, epoch, Rs, Rm, Vm, delta_Vm) %>% group_by(cell) %>% filter(any(delta_Vm > 10))
select(epoch_stats, cell, epoch, Vm, n_spont) %>% group_by(cell) %>% filter(any(n_spont > 5))


## Compare first, pre, post
p4.1 <- (
    select(epoch_stats, cell, condition, epoch_cond, y=duration_mean)
    %>% ggplot(aes(epoch_cond, y, group=cell))
    + geom_line()
    + geom_point()
    + ylab("Duration (s)")
    + xlab("Epoch")
)
p4.2 <- p4.1 %+% select(epoch_stats, epoch_cond, y=slope) + ylab("f-I Slope (Hz/pA)")
pdf("figures/4ap_reversal.pdf", width=2.75, height=1.7)
egg::ggarrange(p4.1 + my.theme, p4.2 + my.theme, nrow=1)
dev.off()


## stats
sweep_stats = (
    read_csv("build/sweep_stats.csv")
    %>% filter(!is.na(firing_duration))
    %>% inner_join(select(epoch_stats, cell, epoch, condition, bird, sire, epoch_cond))
    %>% mutate(epoch_cond=relevel(epoch_cond, "pre"))
    %>% filter(cell!="a2c71415")
)

(fm_rev_dur_4ap <- lmer(firing_duration ~ epoch_cond + (1|cell), filter(sweep_stats, condition=="4ap")))
## (fm_rev_dur_dtx <- lmer(firing_duration ~ epoch_cond + (1|cell), filter(sweep_stats, condition=="dtx")))

(fm_rev_slope <-
   lmer(slope ~ epoch_cond + (1|cell),
        mutate(epoch_stats, epoch_cond=relevel(epoch_cond, "pre")) %>% filter(cell!="a2c71415")
))
