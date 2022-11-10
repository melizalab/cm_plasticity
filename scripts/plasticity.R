library(readr)
library(stringr)
library(tidyr)
library(dplyr)
library(ggplot2)

my.theme <- egg::theme_article() + theme(legend.position="none",
                              	         axis.title=element_text(size=8),
                                         axis.text=element_text(size=6))
plasticity_epochs = (
    read_csv("inputs/plasticity_epochs.csv")
    %>% mutate(cell=str_sub(cell, end=8), condition=factor(condition, levels=c("cr", "noinj", "pr", "bapta")))
)
cell_info = (
    read_csv("build/cell_info.csv")
    %>% mutate(bird=str_sub(bird, end=8), sire=str_sub(sire, end=8), dam=str_sub(dam, end=8))
)
epoch_stats = (
    read_csv("build/epoch_stats.csv")
    %>% inner_join(plasticity_epochs, by=c("cell", "epoch"))
    %>% inner_join(cell_info, by="cell")
)

## Check for exclusions:
select(epoch_stats, cell, epoch, Vm, delta_Rs, delta_Rm) %>% group_by(cell) %>% filter(any(abs(delta_Rs) > 0.3))
select(epoch_stats, cell, epoch, Rs, Rm, Vm, delta_Vm) %>% group_by(cell) %>% filter(any(delta_Vm > 10))
select(epoch_stats, cell, epoch, Vm, n_spont) %>% group_by(cell) %>% filter(any(n_spont > 5))
## -> Remove bad epochs and cells from plasticity_epochs.csv

## select first and last epochs for each cell and tag them
## drop narrow-spiking cells (note: assumes that spike width remains ~constant from first to last)
first_last = (
    epoch_stats
    %>% arrange(cell, epoch)
    %>% group_by(cell)
    %>% mutate(epoch_cond=ifelse(row_number()==1, "first", ifelse(row_number()==n(), "last", "mid")))
    %>% filter(epoch_cond %in% c("first", "last"))
    %>% filter(spike_width > 0.9)
    %>% arrange(cell, epoch)
)

## First, we need to see how long the recording needs to last for plasticity to happen  
fl_cr = filter(first_last, condition=="cr")
## compute deltas
dt_cr = (
    fl_cr
    %>% group_by(cell)
    %>% summarize(
	 condition=first(condition),
	 duration=diff(duration_mean),
	 time=diff(time)
    )
)

p1.1 <- (
    dt_cr
    %>% ggplot(aes(time, duration))
    + geom_point(fill="white", shape=21, size=3)
    + ylab("Δ Duration (s)")
    + xlab("Time (s)")
)


## All conditions:
## drop neurons where time is less than 400 s (need enough time to see plasticity)
too_short = (
    first_last
    %>% group_by(cell)
    %>% filter(last(time) < 400)
    %>% select(cell, epoch, condition, time)
)
fl_all = anti_join(first_last, too_short, by="cell")
dt_all = (
    fl_all
    %>% group_by(cell)
    %>% summarize(
	 condition=first(condition),
         duration=diff(duration_mean),
	 slope=diff(slope),
         Rs=diff(Rs),
         Rm=diff(Rm),
         Vm=diff(Vm),
         rheobase=diff(rheobase),
	 )
    %>% inner_join(cell_info, by="cell")
)

## CR only
fl_cr = filter(fl_all, condition=="cr")
dt_cr = filter(dt_all, condition=="cr")

## duration for first and last
p1.2 <- (
    ggplot(fl_cr, aes(epoch_cond, duration_mean, group=cell))
    + geom_line()
    + geom_point(fill="white", shape=21, size=2)
    + ylab("Duration (s)")
    + xlab("Epoch")
)

## change in duration (last - first) - maybe exclude?
p1.3 <- (
    ggplot(dt_cr, aes(condition, duration))
    + geom_boxplot(width=.1, alpha=0.5)
    + geom_point(fill="white", shape=21, size=2)
    + ylab("Δ Duration (s)")
    + xlab("")
)

## CR: correlate change in duration with other variables
p1.4 <- (
   dt_cr
   %>% pivot_longer(c(slope, Rs, Rm, Vm, rheobase), names_to="measure")
   %>% ggplot(aes(duration, value))
    + facet_wrap(vars(measure), nrow=1, scales="free", strip.position="left")
    + geom_point(fill="white", shape=21, size=3)
    + stat_smooth(method=lm)
    + ylab("Δ")
    + xlab("Δ Duration (s)")
)

## PR:
p1.2 <- (
     filter(fl_all, condition=="pr")
    %>% ggplot(aes(epoch_cond, duration_mean, group=cell))
    + geom_line()
    + geom_point(fill="white", shape=21, size=2)
    + ylab("Duration (s)")
    + xlab("Epoch")
)


## Compare first and last for CR, Noinj, BAPTA
p2 <- (
    filter(fl_all, condition!="pr")
    %>% ggplot(aes(epoch_cond, duration_mean, group=cell))
    + facet_wrap(vars(condition), nrow=1)
    + geom_line()
    + geom_point(fill="white", shape=21, size=3)
    + ylab("Duration (s)")
    + xlab("Epoch")
)



p2 <- (
    filter(fl_all, condition!="pr")
    %>% ggplot(aes(epoch_cond, slope, group=cell))
    + facet_wrap(vars(condition), nrow=1)
    + geom_line()
    + geom_point(fill="white", shape=21, size=3)
    + ylab("f-I Slope (Hz/pA)")
    + xlab("Epoch")
)



p3 <- (
    ggplot(dt_cr, aes(duration, value))
    + facet_wrap(vars(measure), nrow=1, scales="free", strip.position="left")
    + geom_point(fill="white", shape=21, size=3)
    + stat_smooth(method=lm)
    + ylab("Δ")
    + xlab("Δ Duration (s)")
)

## Statistics: 
library(lme4)
library(emmeans)

## first the basic epoch-level model
(fm_e <- lmer(duration ~ condition + (1|bird), dt_all))

## Full analysis uses sweeps instead of epochs so that the LMM will do some partial pooling.
sweep_stats = (
    read_csv("build/sweep_stats.csv")
    %>% filter(!is.na(firing_duration))
    %>% inner_join(select(fl_all, cell, epoch, condition, bird, sire, epoch_cond))
)
(fm_s <- lmer(log10(firing_duration) ~ condition*epoch_cond + (1|cell) + (1|bird), sweep_stats))

## use emmeans to calculate contrasts
## 1. last - first for each condition
em_delta <- (
    fm_s
    %>% emmeans(~ epoch_cond*condition)
    %>% contrast("revpairwise", by="condition")
)
p4 <- (
    confint(em_delta, level=0.50, type="response")
    %>% ggplot(aes(condition, ratio, ymin=lower.CL, ymax=upper.CL))
    + geom_linerange(size=1.5)
    + geom_linerange(data=confint(em_delta, level=0.90, type="response"))
    + geom_point(size=2.5, shape=21, fill="white")
    + geom_hline(yintercept=1.0)
    + scale_y_continuous("Δ Duration", labels = scales::percent)
)
pdf("figures/duration_change.pdf", width=6, height=4)
print(p4 + my.theme)
dev.off()

## post-hoc comparisons:
emmeans(fm_s, ~ epoch_cond*condition) %>% contrast(interaction="revpairwise")