### Quantify plasticity in CR, PR, minimal injection and BAPTA-AM
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

plasticity_epochs = (
    read_csv("inputs/plasticity_epochs.csv")
    %>% mutate(cell=str_sub(cell, end=8), condition=factor(condition, levels=c("cr", "pr", "noinj", "bapta-am", "k4-bapta")))
)
cell_info = (
    read_csv("build/cell_info.csv")
    %>% mutate(bird=str_sub(bird, end=8), sire=str_sub(sire, end=8), dam=str_sub(dam, end=8))
)
## drop narrow-spiking cells (note: assumes that spike width remains ~constant from first to last)
epoch_stats = (
    read_csv("build/epoch_stats.csv")
    %>% inner_join(plasticity_epochs, by=c("cell", "epoch"))
    %>% inner_join(cell_info, by="cell")
    %>% arrange(cell, epoch)
    %>% group_by(cell)
    %>% mutate(epoch_cond=ifelse(row_number()==1, "first", ifelse(row_number()==n(), "last", "mid")))
    %>% filter(spike_width > 0.9)
    %>% arrange(cell, epoch)
)

## Check for exclusions:
select(epoch_stats, cell, epoch, Vm, delta_Rs, delta_Rm) %>% group_by(cell) %>% filter(any(abs(delta_Rs) > 0.3))
select(epoch_stats, cell, epoch, Rs, Rm, Vm, delta_Vm) %>% group_by(cell) %>% filter(any(delta_Vm > 10))
select(epoch_stats, cell, epoch, Vm, n_spont) %>% group_by(cell) %>% filter(any(n_spont > 5))
## -> Remove bad epochs and cells from plasticity_epochs.csv

## First, we need to see how long the recording needs to last for plasticity to happen  
## compute deltas
dt_all = (
    epoch_stats
    %>% group_by(cell)
    %>% mutate(time = time - first(time), delta_duration = duration_mean - first(duration_mean))
)

p1.1a <- (
    filter(dt_all, condition=="cr", epoch_cond=="last")
    %>% select(x=time, delta_duration)
    %>% ggplot(aes(x, delta_duration))
    + geom_point()
    + ylab("Δ Duration (s)")
    + xlab("Time (s)")
)
p1.1b <- (
    p1.1a %+%
    (filter(dt_all, condition=="cr", epoch_cond=="last") %>% select(x=cum_spikes, delta_duration))
    + xlab("Spikes")
)
pdf("figures/cr_duration_time_spikes.pdf", width=2.3, height=1.9)
egg::ggarrange(p1.1a + my.theme, p1.1b + my.theme, nrow=2)
dev.off()

p2.1a <- (
    p1.1a %+%
    (filter(dt_all, condition=="pr", epoch_cond=="last") %>% select(x=cum_spikes, delta_duration))
)
p2.1b <- (
    p1.1a %+%
    (filter(dt_all, condition=="pr", epoch_cond=="last") %>% select(x=cum_spikes, delta_duration))
    + xlab("Spikes")
)
pdf("figures/pr_duration_time_spikes.pdf", width=2.3, height=1.9)
egg::ggarrange(p2.1a + my.theme, p2.1b + my.theme, nrow=2)
dev.off()

## All conditions:
## drop neurons where time is less than 400 s (need enough time to see plasticity)
too_short = (
    epoch_stats
    %>% group_by(cell)
    %>% filter(epoch_cond=="last", time < 400)
    %>% select(cell, epoch, condition, time)
)
fl_all = (
    filter(epoch_stats, epoch_cond %in% c("first", "last"))
    %>% anti_join(too_short, by="cell")
)
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
	 spikes=diff(cum_spikes),
	 time=diff(time)
	 )
    %>% inner_join(cell_info, by="cell")
)

## CR: duration for first and last
p1.2 <- (
    filter(fl_all, condition=="cr")
    %>% select(cell, epoch_cond, y=duration_mean, sex)
    %>% ggplot(aes(epoch_cond, y, group=cell))
    + geom_line()
    + geom_point(size=1)
    + ylab("Duration (s)")
    + xlab("Epoch")
)
p1.3 <- p1.2 %+% (filter(fl_all, condition=="cr") %>% select(cell, epoch_cond, y=slope)) + ylab("f-I Slope (Hz/pA)")
pdf("figures/cr_delta_duration_slope.pdf", width=2.3, height=1.7)
egg::ggarrange(p1.2 + my.theme, p1.3 + my.theme, nrow=1)
dev.off()


## change in duration (last - first) - maybe exclude?
## p <- (
##     ggplot(dt_cr, aes(condition, duration))
##     + geom_boxplot(width=.1, alpha=0.5)
##     + geom_point(fill="white", shape=21, size=2)
##     + ylab("Δ Duration (s)")
##     + xlab("")
## )

## PR: duration/slope for first and last
p2.2 <- p1.2 %+% (filter(fl_all, condition=="pr") %>% select(cell, epoch_cond, y=duration_mean))
p2.3 <- p1.2 %+% (filter(fl_all, condition=="pr") %>% select(cell, epoch_cond, y=slope))
pdf("figures/pr_delta_duration_slope.pdf", width=2.3, height=1.7)
egg::ggarrange(p2.2 + my.theme, p2.3 + my.theme, nrow=1)
dev.off()

## Compare first and last for Noinj, BAPTA-AM. K4-BAPTA not included b/c the K+ internal concentration was probably too high.
p3.1 <- (
    filter(fl_all, condition %in% c("noinj","bapta-am"))
    %>% select(cell, epoch_cond, condition, y=duration_mean)
    %>% ggplot(aes(epoch_cond, y, group=cell))
    + facet_wrap(vars(condition), nrow=1)
    + geom_line()
    + geom_point(size=1)
    + ylab("Duration (s)")
    + xlab("Epoch")
)
p3.2 <- (
    p3.1 %+% (filter(fl_all, condition %in% c("noinj","bapta-am"))
    %>% select(cell, epoch_cond, condition, y=slope))
    + ylab("f-I Slope (Hz/pA)")
)
pdf("figures/noinj-bapta_delta_duration_slope.pdf", width=1.9, height=3.4)
egg::ggarrange(p3.1 + my.theme, p3.2 + my.theme, nrow=2)
dev.off()

p3.3 <- (
    filter(dt_all, condition %in% c("noinj", "bapta-am"))
    %>% ggplot(aes(spikes, duration, color=condition))
    + geom_point()
    + ylab("Δ Duration (s)")
    + xlab("Spikes")
)
pdf("figures/noinj-bapta_delta_duration_spikes.pdf", width=3.4, height=3.4)
print(p3.3 + my.theme)
dev.off()

## Statistics: 

## Some analyses use sweeps instead of epochs so that the LMM will do some partial pooling.
sweep_stats = (
    read_csv("build/sweep_stats.csv")
    %>% filter(!is.na(firing_duration))
    %>% inner_join(select(fl_all, cell, epoch, condition, bird, sex, sire, epoch_cond))
)

## CR: effect of sex
(fm_ds <- lmer(firing_duration ~ epoch_cond*sex + (1 + epoch_cond|cell) + (1|bird), filter(sweep_stats, condition=="cr")))
anova(fm_ds)

## CR vs PR: Vm
(fm_vm <- lmer(Vm ~ condition + (1|cell) + (1|bird), filter(sweep_stats, epoch_cond=="first")))
(fm_rm <- lmer(Rm ~ condition + (1|cell) + (1|bird), filter(sweep_stats, epoch_cond=="first")))


## All conditions: duration
(fm_d <- lmer(firing_duration ~ epoch_cond*condition + (1 + epoch_cond|cell) + (1|bird), sweep_stats))
## use emmeans to calculate contrasts
## 1. last - first for each condition
(em_d <- (
    fm_d
    %>% emmeans(~ epoch_cond*condition)
    %>% contrast("revpairwise", by="condition")
))
(ci_d <- bind_cols(confint(em_d, level=0.50, type="response"),
                  confint(em_d, level=0.90, type="response") %>% select(lower.CL.90=lower.CL, upper.CL.90=upper.CL)))

## post-hoc comparisons:
emmeans(fm_d, ~ epoch_cond*condition) %>% contrast(interaction="revpairwise")

## all conditions: slope
fm_s <- lmer(slope ~ epoch_cond*condition + (1|cell) + (1|bird), fl_all)
anova(fm_s)		  
em_s <- (
    fm_s
    %>% emmeans(~ epoch_cond*condition)
    %>% contrast("revpairwise", by="condition")
)
ci_s <- bind_cols(confint(em_s, level=0.50, type="response"),
                  confint(em_s, level=0.90, type="response") %>% select(lower.CL.90=lower.CL, upper.CL.90=upper.CL))
emmeans(fm_s, ~ epoch_cond*condition) %>% contrast(interaction="revpairwise")

p7.1 <- (
    ci_d
    %>% ggplot(aes(condition, estimate, ymin=lower.CL, ymax=upper.CL))
    + geom_linerange(linewidth=1.5)
    + geom_linerange(aes(ymin=lower.CL.90, ymax=upper.CL.90))
    + geom_point(size=2.5)
    + geom_hline(yintercept=0.0)
    + scale_y_continuous("Δ Duration (s)") #, labels = scales::percent)
)

p7.2 <- p7.1 %+% ci_s + scale_y_continuous("Δ Slope (Hz/pA)")
pdf("figures/duration_slope_summary.pdf", width=1.8, height=2.8)
egg::ggarrange(p7.1 + my.theme, p7.2 + my.theme, nrow=2)
dev.off()

## these are not significant
fm_r <- lmer(Rm ~ epoch_cond*condition + (1|cell) + (1|bird), fl_all)
anova(fm_r)
fm_v <- lmer(Vm ~ epoch_cond*condition + (1|cell) + (1|bird), fl_all)
anova(fm_v)
(em_v <- (
    fm_v
    %>% emmeans(~ epoch_cond*condition)
    %>% contrast("revpairwise", by="condition")
))
(ci_v <- bind_cols(confint(em_v, level=0.50, type="response"),
                  confint(em_v, level=0.90, type="response") %>% select(lower.CL.90=lower.CL, upper.CL.90=upper.CL)))

## all conditions: correlate change in duration with other variables
p7.3 <- (
   dt_all 
   %>% pivot_longer(c(slope, Rm, Vm, rheobase), names_to="measure")
   %>% ggplot(aes(duration, value))
    + facet_wrap(vars(measure), nrow=2, scales="free", strip.position="left")
    + geom_point(aes(color=condition), fill=NA, size=1.0)
    + stat_smooth(method=lm, linewidth=0.5)
    + ylab("")
    + xlab("Δ Duration (s)")
)
pdf("figures/all_duration_corr.pdf", width=2.9, height=2.4)
print(p7.3 + my.theme + theme(panel.spacing.x=unit(0, "in")))
dev.off()

cor.test(~ duration + slope, dt_all)
cor.test(~ duration + rheobase, dt_all)
cor.test(~ duration + Rm, dt_all)
cor.test(~ duration + Vm, dt_all)