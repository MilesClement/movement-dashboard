import matplotlib
import pandas as pd
import numpy as np
import pickle
import urllib.request
import dateutil.parser
import dateutil.rrule
import dateutil.tz
import datetime
import warnings
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.patheffects as pe

warnings.filterwarnings('ignore')

matplotlib.rcParams.update({
    'font.size': 13,
    'timezone': 'Europe/London',
    'figure.max_open_warning': False
})

tzLocal = dateutil.tz.gettz('Europe/London')
dateToday = datetime.datetime.combine(datetime.date.today(), datetime.datetime.min.time()).replace(tzinfo=tzLocal)
dateBaselineEnd = datetime.datetime.strptime('2020-03-15T23:59:59Z', '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=tzLocal)
plottableTypes = ['int16', 'int32', 'int64', 'float16', 'float32', 'float64']
govChartStart = datetime.datetime.strptime('2020-03-01T00:00:00Z', '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=tzLocal)

def makeRelativeToBaseline(pdInput, maxMissing15Min = 4):  
    pdTrafficAnalysis = pdInput.copy()
    
    pdTrafficAnalysis.insert(0, 'Date', pdTrafficAnalysis.index.to_series().apply(lambda t: t.date()))
    pdTrafficAnalysis.insert(0, 'Day of week', pdTrafficAnalysis.index.to_series().apply(lambda t: t.strftime('%A')))
    pdTrafficAnalysis.insert(1, 'Time of day', pdTrafficAnalysis.index.to_series().apply(lambda t: t.strftime('%H:%M:%S')))

    # Take each day with complete data, and calculate a sum of vehicles per day
    # then convert it to an average per day of the week using the median
    # MUST BE 15 MINUTE DATA AS INPUT FOR THIS...
    pdTrafficDayOfWeekAverage = pdTrafficAnalysis[ : dateBaselineEnd] \
        .groupby(['Date', 'Day of week'], as_index=False) \
        .sum(min_count=24 * 4 - maxMissing15Min) \
        .groupby(['Day of week'], as_index=False) \
        .median()

    pdTrafficRecent = pdTrafficAnalysis[govChartStart :] \
        .groupby(['Date', 'Day of week'], as_index=False) \
        .sum(min_count=85)  \
        .replace(0, np.nan)
    # Normally minimum 90... (24 * 4 = 96)

    pdTrafficRecentRelativePc = pdTrafficRecent[pdTrafficRecent.select_dtypes(plottableTypes).columns]
    pdTrafficRecentRelativePc.index = pdTrafficRecent['Date']
    #pdTrafficRecentRelativePc.insert(0, 'Day of week', pdTrafficRecentRelativePc.index.to_series().apply(lambda t: t.strftime('%A')))

    def convertToPercentage(row):
        dayOfWeek = row.name.strftime('%A')
        dayOfWeekNormal = pdTrafficDayOfWeekAverage[pdTrafficDayOfWeekAverage['Day of week'] == dayOfWeek].iloc[:, 1:].values[0]
        return (row / dayOfWeekNormal * 100)

    pdTrafficRecentRelativePc = pdTrafficRecentRelativePc.apply(convertToPercentage, axis=1)

    # Output tables:
    #pdTrafficDayOfWeekAverage
    #pdTrafficRecentRelativePc
    
    return pdTrafficRecentRelativePc

def plotTraffic(pdTrafficRecentRelativePc, dfMedianPc, tsAdditionalDetail, fullLegend = False, normalLineAlpha=0.5):
    fig, ax = plt.subplots(1,1, figsize=(18,9), constrained_layout=True)

    ax.set_xlabel('Date')
    ax.set_ylim([0, 130])
    ax.set_ylabel('Percentage')

    timeLocatorMajor = mdates.AutoDateLocator(minticks=15, maxticks=60)
    conciseZeroFormats = ['', '%Y', '%b', '%d-%b', '%H:%M', '%H:%M']
    conciseOffsetFormats = ['', '%Y', '%b-%Y', '%d-%b-%Y-%b', '%d-%b-%Y', '%d-%b-%Y %H:%M']
    ax.xaxis.set_tick_params(which='major')
    ax.xaxis.set_major_locator(timeLocatorMajor)
    ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator=timeLocatorMajor, zero_formats=conciseZeroFormats, offset_formats=conciseOffsetFormats))

    ax.grid(linestyle='--')

    tsAnnotationOffset = 1
    annotationColours = iter(plt.get_cmap('Dark2').colors)
    tsAnnotationOffsetAlternator = -8

    for ts in reversed(sorted(list(pdTrafficRecentRelativePc.columns))):
        dfTs = pdTrafficRecentRelativePc[ts]
        dfTs.index = dfTs.index.map(lambda d: datetime.datetime.combine(d, datetime.time.min).replace(tzinfo=tzLocal))
        dfTs = dfTs[(dfTs < 160) & (dfTs > 10)] # Sanity limits :-)

        if ts in tsAdditionalDetail.keys():
            seriesColour = next(annotationColours)

            if fullLegend == True:
                ax.plot(dfTs, color=seriesColour, alpha=0.8, linewidth=1.5, label=tsAdditionalDetail[ts], zorder=2)
            else:
                ax.plot(dfTs, color=seriesColour, alpha=0.8, linewidth=1.5)
                
                arrowDay = dateToday - pd.Timedelta(days=tsAnnotationOffset)

                arrowPointsAt = list(dfTs[dfTs.index == arrowDay].to_dict().values())
                arrowPointsAt = None if len(arrowPointsAt) <= 0 else arrowPointsAt[0]
                arrowMedian = list(dfMedianPc[dfMedianPc.index == arrowDay].to_dict().values())
                arrowMedian = None if len(arrowMedian) <= 0 else arrowMedian[0]

                shiftAttempt = 0
                while (arrowPointsAt is None or abs(arrowPointsAt - arrowMedian) < 3.5) and shiftAttempt < 5:
                    tsAnnotationOffset = tsAnnotationOffset + 1
                    shiftAttempt = shiftAttempt + 1
                    arrowDay = dateToday - pd.Timedelta(days=tsAnnotationOffset)
                    arrowPointsAt = list(dfTs[dfTs.index == arrowDay].to_dict().values())
                    arrowPointsAt = None if len(arrowPointsAt) <= 0 else arrowPointsAt[0]
                    arrowMedian = list(dfMedianPc[dfMedianPc.index == arrowDay].to_dict().values())
                    arrowMedian = None if len(arrowMedian) <= 0 else arrowMedian[0]

                tsAnnotationOffsetAlternator = -tsAnnotationOffsetAlternator

                ax.annotate(tsAdditionalDetail[ts],
                    xy=(arrowDay, arrowPointsAt),
                    xycoords='data',
                    xytext=(arrowDay, max(12.5, arrowPointsAt + ((+20 + tsAnnotationOffsetAlternator) if arrowPointsAt > arrowMedian else (-20 + tsAnnotationOffsetAlternator)))),
                    textcoords='data',
                    arrowprops=dict(facecolor='black', shrink=0.01, width=0.2, headwidth=4.5),
                    horizontalalignment='center',
                    verticalalignment='top',
                    fontsize=11,
                    path_effects=[pe.withStroke(linewidth=4, foreground='#ffffffa0')]
                )
                ax.annotate('●',
                    xy=(arrowDay, max(7, arrowPointsAt + ((+25 + tsAnnotationOffsetAlternator) if arrowPointsAt > arrowMedian else (-26 + tsAnnotationOffsetAlternator)))),
                    xycoords='data',
                    xytext=(arrowDay, max(7, arrowPointsAt + ((+25 + tsAnnotationOffsetAlternator) if arrowPointsAt > arrowMedian else (-26 + tsAnnotationOffsetAlternator)))),
                    textcoords='data',
                    horizontalalignment='center',
                    verticalalignment='top',
                    fontsize=14,
                    color=seriesColour
                )
                tsAnnotationOffset = tsAnnotationOffset + 3

        else:
            ax.plot(dfTs, color='#909090', alpha=normalLineAlpha, linewidth=0.35)

    for date in dfMedianPc.index:
        if date.strftime('%A') in ['Saturday', 'Sunday']:
            #print(date)
            ax.axvspan(
                date - pd.Timedelta(days=0.5),
                date + pd.Timedelta(days=0.5),
                alpha=0.1,
                color='#606060',
                zorder=3
            )

    ax.plot(dfMedianPc, color='#f64a8a', linewidth=2.0, marker='s', markersize=10, label='Median')
    plt.xticks(ha='center')
    plt.legend(loc='upper right')
    
    return [plt, fig, ax]
